﻿/* Copyright (c) 2020 Rick (rick 'at' gibbed 'dot' us)
 *
 * This software is provided 'as-is', without any express or implied
 * warranty. In no event will the authors be held liable for any damages
 * arising from the use of this software.
 *
 * Permission is granted to anyone to use this software for any purpose,
 * including commercial applications, and to alter it and redistribute it
 * freely, subject to the following restrictions:
 *
 * 1. The origin of this software must not be misrepresented; you must not
 *    claim that you wrote the original software. If you use this software
 *    in a product, an acknowledgment in the product documentation would
 *    be appreciated but is not required.
 *
 * 2. Altered source versions must be plainly marked as such, and must not
 *    be misrepresented as being the original software.
 *
 * 3. This notice may not be removed or altered from any source
 *    distribution.
 */

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Gibbed.IO;

namespace Gibbed.Disrupt.FileFormats
{
    public class BinaryObject
    {
        #region Fields
        private long _Position;
        private uint _NameHash;
        private readonly Dictionary<uint, byte[]> _Fields;
        private readonly List<BinaryObject> _Children;
        #endregion

        public BinaryObject()
        {
            this._Fields = new Dictionary<uint, byte[]>();
            this._Children = new List<BinaryObject>();
        }

        #region Properties
        public long Position
        {
            get { return this._Position; }
            set { this._Position = value; }
        }

        public uint NameHash
        {
            get { return this._NameHash; }
            set { this._NameHash = value; }
        }

        public Dictionary<uint, byte[]> Fields
        {
            get { return this._Fields; }
        }

        public List<BinaryObject> Children
        {
            get { return this._Children; }
        }

        public byte[] this[uint hash]
        {
            get
            {
                if (this._Fields.ContainsKey(hash) == false)
                {
                    return null;
                }

                return this._Fields[hash];
            }

            set
            {
                if (value == null)
                {
                    this._Fields.Remove(hash);
                }
                else
                {
                    this._Fields[hash] = value;
                }
            }
        }

        public byte[] this[string name]
        {
            get { return this[Hashing.CRC32.Compute(name)]; }
            set { this[Hashing.CRC32.Compute(name)] = value; }
        }
#endregion

        public void Serialize(
            Stream output,
            ref uint totalObjectCount,
            ref uint totalValueCount,
            Endian endian)
        {
            totalObjectCount += (uint)this.Children.Count;
            totalValueCount += (uint)this._Fields.Count;

            WriteCount(output, this.Children.Count, false, endian);

            output.WriteValueU32(this.NameHash, endian);

            WriteCount(output, this._Fields.Count, false, endian);
            // If values[0] = values[2] set breakpoint
            byte[] v0 = new byte[4];
            byte[] v2 = new byte[4];
            int i = 0;
            foreach (var kv in this._Fields)
            {
                if (i == 0)
                    v0 = kv.Value;
                else if (i == 2)
                    v2 = kv.Value;
                i++;
            }

            bool useFE = false;
            bool newFE = false;
            if (v0.SequenceEqual(v2) && this._Fields.Count >= 3 && v0.Length > 0 && v2.Length > 0)
            {
                useFE = true;
            }
            else
            {
                List<byte[]> values = new List<byte[]>();
                foreach (var kv in this._Fields)
                {
                    byte[] currVal = kv.Value;
                    if (currVal.Length == 4 && currVal[0] == 0 && currVal[1] == 0 && currVal[2] == 0 && currVal[3] == 0)
                        continue;
                    int count = 0;
                    foreach (byte[] prevVal in values)
                    {
                        if (output.Position > 0x775000 && prevVal.SequenceEqual(currVal) && prevVal.Length >= 4 && currVal.Length >= 4)
                        {
                            newFE = true;
                            Console.WriteLine("Child num: " + count);
                        }
                        count++;
                    }
                    values.Add(kv.Value);
                }
            }
            if (newFE)
            {
                Console.WriteLine("Found new format");
                Console.WriteLine("Current pos: " + output.Position.ToString("X8"));
            }
            i = 0;
            long initPos = 0;
            foreach (var kv in this._Fields)
            {
                output.WriteValueU32(kv.Key, endian);
                if (!useFE || i != 2)
                {
                    WriteCount(output, kv.Value.Length, false, endian);
                    if (i == 0)
                        initPos = output.Position;
                    output.WriteBytes(kv.Value);
                }
                else
                {
                    output.WriteValueU8(0xFE);
                    // Need to write the number of bytes between
                    byte offset = (byte) (output.Position - initPos);
                    output.WriteBytes(new byte[] { offset, 0, 0, 0 });
                }
                i++;
            }

            foreach (var child in this.Children)
            {
                child.Serialize(
                    output,
                    ref totalObjectCount,
                    ref totalValueCount,
                    endian);
            }
        }

        // Read node, calls leaf node version
        public static BinaryObject Deserialize(
            BinaryObject parent,
            Stream input,
            List<BinaryObject> pointers,
            Endian endian)
        {
            long position = input.Position;

            int count = input.ReadByte();
            input.Position--;

            if (count == 0xFE)
            {
                Console.WriteLine("Pointer");
            }

            var childCount = ReadCount(input, out var isOffset, endian);

            if (isOffset == true)
            {
                return pointers[(int)childCount];
            }

            var child = new BinaryObject();
            child.Position = position;
            pointers.Add(child);

            child.Deserialize(input, childCount, pointers, endian);
            return child;
        }

        // Leaf nodes, can be recursive
        private void Deserialize(
            Stream input,
            uint childCount,
            List<BinaryObject> pointers,
            Endian endian)
        {

            this.NameHash = input.ReadValueU32(endian);

            var valueCount = ReadCount(input, out var isOffset, endian);
            if (isOffset == true)
            {
                throw new NotImplementedException();
            }

            this._Fields.Clear();
            for (var i = 0; i < valueCount; i++)
            {
                var nameHash = input.ReadValueU32(endian);
                byte[] value;

                var position = input.Position;
                var size = ReadCount(input, out isOffset, endian);
                if (input.Position > 0x775000)
                {
                    Console.WriteLine("Test");
                }
                if (isOffset == true)
                {
                    input.Seek(position - size, SeekOrigin.Begin);

                    size = ReadCount(input, out isOffset, endian);
                    if (isOffset == true)
                    {
                        throw new FormatException("offset to offset isn't supported");
                    }

                    value = input.ReadBytes((int)size);

                    input.Seek(position, SeekOrigin.Begin);
                    ReadCount(input, out _, endian);
                }
                else
                {
                    value = input.ReadBytes((int)size);
                }

                this._Fields.Add(nameHash, value);
            }

            this.Children.Clear();
            for (var i = 0; i < childCount; i++)
            {
                this.Children.Add(Deserialize(this, input, pointers, endian));
            }
        }

        public static uint ReadCount(Stream input, out bool isOffset, Endian endian)
        {
            var value = input.ReadValueU8();
            isOffset = false;

            if (value < 0xFE)
            {
                return value;
            }

            isOffset = value != 0xFF;
            return input.ReadValueU32(endian);
        }

        public static void WriteCount(Stream output, int value, bool isOffset, Endian endian)
        {
            WriteCount(output, (uint)value, isOffset, endian);
        }

        public static void WriteCount(Stream output, uint value, bool isOffset, Endian endian)
        {
            if (isOffset == true || value >= 0xFE)
            {
                output.WriteValueU8((byte)(isOffset == true ? 0xFE : 0xFF));
                output.WriteValueU32(value, endian);
                return;
            }

            output.WriteValueU8((byte)(value & 0xFF));
        }
    }
}
