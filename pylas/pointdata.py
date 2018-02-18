import numpy as np

from .compression import decompress_stream
from .pointdimensions import get_dtype_of_format_id


class NumpyPointData:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __len__(self):
        return self.data.shape[0]

    def write_to(self, out):
        raw_bytes = self.data.tobytes()
        out.write(raw_bytes)

    @classmethod
    def from_stream(cls, stream, point_format_id, count):
        points_dtype = get_dtype_of_format_id(point_format_id)

        point_data_buffer = stream.read(count * points_dtype.itemsize)
        data = np.frombuffer(point_data_buffer, dtype=points_dtype, count=count)
        return cls(data)

    @classmethod
    def from_compressed_stream(cls, compressed_stream, point_format_id, count, laszip_vlr):
        uncompressed = decompress_stream(compressed_stream, point_format_id, count, laszip_vlr)
        return cls(uncompressed)
