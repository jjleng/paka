import struct
from collections import namedtuple
from typing import Any, BinaryIO, Dict, List, Union

Slice = namedtuple("Slice", ["value", "length"])

GGUFValueType = {
    "UINT8": 0,
    "INT8": 1,
    "UINT16": 2,
    "INT16": 3,
    "UINT32": 4,
    "INT32": 5,
    "FLOAT32": 6,
    "BOOL": 7,
    "STRING": 8,
    "ARRAY": 9,
    "UINT64": 10,
    "INT64": 11,
    "FLOAT64": 12,
}


def read_string(file: BinaryIO, version: int, little_endian: bool) -> Slice:
    length = read_versioned_size(file, version, little_endian)
    value = file.read(length.value).decode("utf-8")
    return Slice(value=value, length=length.length + length.value)


def read_versioned_size(file: BinaryIO, version: int, little_endian: bool) -> Slice:
    endian = "<" if little_endian else ">"
    if version == 1:
        length_value = struct.unpack(endian + "I", file.read(4))[0]
        length_size = 4
    elif version in [2, 3]:
        length_value = struct.unpack(endian + "Q", file.read(8))[0]
        length_size = 8
    else:
        raise ValueError(f"Unsupported version: {version}")
    return Slice(value=length_value, length=length_size)


def read_metadata_value(
    file: BinaryIO, value_type: int, version: int, little_endian: bool
) -> Slice:
    endian = "<" if little_endian else ">"
    if value_type == GGUFValueType["UINT8"]:
        return Slice(value=struct.unpack(endian + "B", file.read(1))[0], length=1)
    elif value_type == GGUFValueType["INT8"]:
        return Slice(value=struct.unpack(endian + "b", file.read(1))[0], length=1)
    elif value_type == GGUFValueType["UINT16"]:
        return Slice(value=struct.unpack(endian + "H", file.read(2))[0], length=2)
    elif value_type == GGUFValueType["INT16"]:
        return Slice(value=struct.unpack(endian + "h", file.read(2))[0], length=2)
    elif value_type == GGUFValueType["UINT32"]:
        return Slice(value=struct.unpack(endian + "I", file.read(4))[0], length=4)
    elif value_type == GGUFValueType["INT32"]:
        return Slice(value=struct.unpack(endian + "i", file.read(4))[0], length=4)
    elif value_type == GGUFValueType["FLOAT32"]:
        return Slice(value=struct.unpack(endian + "f", file.read(4))[0], length=4)
    elif value_type == GGUFValueType["BOOL"]:
        return Slice(value=struct.unpack(endian + "B", file.read(1))[0] != 0, length=1)
    elif value_type == GGUFValueType["STRING"]:
        return read_string(file, version, little_endian)
    elif value_type == GGUFValueType["ARRAY"]:
        array_type = struct.unpack(endian + "I", file.read(4))[0]
        array_length = read_versioned_size(file, version, little_endian)
        length = 4 + array_length.length
        array_values = []
        for _ in range(array_length.value):
            metadata_value = read_metadata_value(
                file, array_type, version, little_endian
            )
            array_values.append(metadata_value.value)
            length += metadata_value.length
        return Slice(value=array_values, length=length)
    elif value_type == GGUFValueType["UINT64"]:
        return Slice(value=struct.unpack(endian + "Q", file.read(8))[0], length=8)
    elif value_type == GGUFValueType["INT64"]:
        return Slice(value=struct.unpack(endian + "q", file.read(8))[0], length=8)
    elif value_type == GGUFValueType["FLOAT64"]:
        return Slice(value=struct.unpack(endian + "d", file.read(8))[0], length=8)
    else:
        raise ValueError(f"Unsupported metadata type: {value_type}")


def gguf(local_file_path: str) -> Dict[str, Any]:
    with open(local_file_path, "rb") as file:
        # Read and check the magic number
        magic_number = file.read(4)
        if magic_number != b"GGUF":
            raise ValueError(
                "Not a valid gguf file: does not start with GGUF magic number"
            )

        # Determine the endianness and read the version
        version = struct.unpack("<I", file.read(4))[0]
        if version & 65535:
            little_endian = True
        else:
            little_endian = False
            file.seek(4, 0)  # Rewind to read the version again in big-endian
            version = struct.unpack(">I", file.read(4))[0]

        if version not in [1, 2, 3]:
            raise ValueError(f"Not a valid gguf file: unsupported version '{version}'")

        # Read the tensor count and key-value count
        tensor_count_slice = read_versioned_size(file, version, little_endian)
        tensor_count = tensor_count_slice.value

        kv_count_slice = read_versioned_size(file, version, little_endian)
        kv_count = kv_count_slice.value

        # Initialize the metadata
        metadata: Dict[str, Any] = {
            "version": version,
            "tensor_count": tensor_count,
            "kv_count": kv_count,
        }

        for _ in range(kv_count):
            key_result = read_string(file, version, little_endian)
            key = key_result.value

            value_type = struct.unpack("<I" if little_endian else ">I", file.read(4))[0]
            if value_type not in GGUFValueType.values():
                raise ValueError(f"Unsupported metadata type: {value_type}")

            value_result = read_metadata_value(file, value_type, version, little_endian)
            metadata[key] = value_result.value

        tensor_infos: List[Dict[str, Union[str, int, List[int]]]] = []
        for _ in range(tensor_count):
            name_result = read_string(file, version, little_endian)
            name = name_result.value

            n_dims = struct.unpack("<I" if little_endian else ">I", file.read(4))[0]
            shape: List[int] = []
            for _ in range(n_dims):
                shape_dim = read_versioned_size(file, version, little_endian)
                shape.append(shape_dim.value)

            dtype = struct.unpack("<I" if little_endian else ">I", file.read(4))[0]
            offset = struct.unpack("<Q" if little_endian else ">Q", file.read(8))[0]

            tensor_infos.append(
                {
                    "name": name,
                    "n_dims": n_dims,
                    "shape": shape,
                    "dtype": dtype,
                    "offset": offset,
                }
            )

        return {"metadata": metadata, "tensor_infos": tensor_infos}


result = gguf("/Users/jleng/Downloads/llama-2-7b-chat.Q4_0.gguf")
metadata, tensor_infos = result["metadata"], result["tensor_infos"]

for k, v in metadata.items():
    if not k.startswith("tokenizer"):
        print(k, v)

print(tensor_infos)
