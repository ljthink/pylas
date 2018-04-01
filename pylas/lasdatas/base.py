import numpy as np

from ..compression import (compress_buffer, create_laz_vlr,
                           uncompressed_id_to_compressed)
from ..point import record, dims
from ..vlrs import known, vlrlist


def scale_dimension(array_dim, scale, offset):
    return (array_dim * scale) + offset


def unscale_dimension(array_dim, scale, offset):
    return (array_dim - offset) / scale


class LasBase(object):
    """ LasBase is the base of all the different LasData classes.
    These classes are objects that the user will interact with to manipulate las datas.

    It connects the point record, header, vlrs together.

    To access points dimensions using this class you have two possibilities

    .. code:: python

        las = pylas.read('some_file.las')
        las.classification
        # or
        las['classification']


    .. note::
        using las['dimension_name']  is not possible with the scaled values of x, y, z


    """

    def __init__(self, *, header, vlrs=None, points=None):
        if points is None:
            points = record.PackedPointRecord.empty(header.point_data_format_id)
        self.__dict__['points_data'] = points
        self.header = header
        self.vlrs = vlrs if vlrs is not None else vlrlist.VLRList()

    @property
    def x(self):
        return scale_dimension(self.X, self.header.x_scale, self.header.x_offset)

    @property
    def y(self):
        return scale_dimension(self.Y, self.header.y_scale, self.header.y_offset)

    @property
    def z(self):
        return scale_dimension(self.Z, self.header.z_scale, self.header.z_offset)

    @x.setter
    def x(self, value):
        self.header.x_offset = np.min(value)
        self.X = unscale_dimension(
            value, self.header.x_scale, self.header.x_offset)

    @y.setter
    def y(self, value):
        self.header.y_offset = np.min(value)
        self.Y = unscale_dimension(
            value, self.header.y_scale, self.header.y_offset)

    @z.setter
    def z(self, value):
        self.header.z_offset = np.min(value)
        self.Z = unscale_dimension(
            value, self.header.z_scale, self.header.z_offset)

    @property
    def points(self):
        """ returns the numpy array representing the points

        Returns
        -------
        the Numpy structured array of points

        """
        return self.points_data.array

    @points.setter
    def points(self, value):
        self.points_data = record.PackedPointRecord(value)

    def __getattr__(self, item):
        """ Automatically called by Python when the attribute
        named 'item' is no found. We use this function to forward the call the
        point record. This is the mechanism used to allow the users to access
        the points dimensions directly through a LasData.

        Parameters
        ----------
        item: str
            name of the attribute, should be a dimension name

        Returns
        -------
        The requested dimension if it exists

        """
        return self.points_data[item]

    def __setattr__(self, key, value):
        """ This is called on every access to an attriute of the instance.
        Again we use this to forward the call the the points record
        But this time checking if the key is actually a dimension name
        """
        if key in dims.DIMENSIONS or key in self.points_data.dimensions_names:
            self.points_data[key] = value
        else:
            super().__setattr__(key, value)

    def __getitem__(self, item):
        return self.points_data[item]

    def __setitem__(self, key, value):
        self.points_data[key] = value

    def update_header(self):
        self.header.point_data_format_id = self.points_data.point_format_id
        self.header.number_of_point_records = len(self.points_data)
        self.header.number_of_points_records_ = len(self.points_data)
        self.header.point_data_record_length = self.points_data.point_size

        if len(self.points_data) > 0:
            self.header.x_max = self.x.max()
            self.header.y_max = self.y.max()
            self.header.z_max = self.z.max()

            self.header.x_min = self.x.min()
            self.header.y_min = self.y.min()
            self.header.z_min = self.z.min()

            unique, counts = np.unique(self.return_number, return_counts=True)
            self.header.number_of_points_by_return = counts

    def write_to(self, out_stream, do_compress=False):
        """ writes the data to a stream

        Parameters
        ----------
        out_stream: file object
            the destination stream, implementing the write method
        do_compress: bool, optional, default False
            Flag to indicate if you want the date to be compressed
        """
        self.update_header()
        raw_vlrs = vlrlist.RawVLRList(v.into_raw() for v in self.vlrs)

        if do_compress:
            try:
                _ = self.vlrs.index('ExtraBytesVlr')
            except ValueError:
                pass
            else:
                raise NotImplementedError('Lazperf cannot compress LAS with extra bytes')

            laz_vrl = create_laz_vlr(self.header.point_data_format_id)
            raw_vlrs.append(known.LasZipVlr(laz_vrl.data()).into_raw())

            self.header.offset_to_point_data = self.header.header_size + raw_vlrs.total_size_in_bytes()
            self.header.point_data_format_id = uncompressed_id_to_compressed(self.header.point_data_format_id)
            self.header.number_of_vlr = len(raw_vlrs)

            compressed_points = compress_buffer(
                np.frombuffer(self.points_data.array, np.uint8),
                laz_vrl.schema,
                self.header.offset_to_point_data,
            )

            self.header.write_to(out_stream)
            self._raise_if_not_expected_pos(out_stream, self.header.header_size)
            raw_vlrs.write_to(out_stream)
            self._raise_if_not_expected_pos(out_stream, self.header.offset_to_point_data)
            out_stream.write(compressed_points.tobytes())
        else:
            self.header.number_of_vlr = len(self.vlrs)
            self.header.offset_to_point_data = self.header.header_size + raw_vlrs.total_size_in_bytes()

            self.header.write_to(out_stream)
            self._raise_if_not_expected_pos(out_stream, self.header.header_size)
            raw_vlrs.write_to(out_stream)
            self._raise_if_not_expected_pos(out_stream, self.header.offset_to_point_data)
            self.points_data.write_to(out_stream)

    @staticmethod
    def _raise_if_not_expected_pos(stream, expected_pos):
        if not stream.tell() == expected_pos:
            raise RuntimeError('Writing, expected to at pos {} but stream is at pos {}'.format(
                expected_pos, stream.tell()
            ))

    def write_to_file(self, filename, do_compress=None):
        """ Writes the las data into a file

        Parameters
        ----------
        filename : str
            The file where the data should be written.
        do_compress: bool, optional, default None
            if None the extension of the filename will be used
        to determine if the data should be compressed
        otherwise the do_compress flag indicate if the data should be compressed
        """
        is_ext_laz = filename.split('.')[-1] == 'laz'
        if is_ext_laz and do_compress is None:
            do_compress = True
        with open(filename, mode='wb') as out:
            self.write_to(out, do_compress=do_compress)

    def write(self, destination, do_compress=None):
        """ Writes to a stream or file

        Parameters
        ----------
        destination: str or file object
            filename or stream to write to
        do_compress: bool, optional, default False
            Flags to indicate if you want to compress the data
        """
        if isinstance(destination, str):
            self.write_to_file(destination)
        else:
            if do_compress is None:
                do_compress = False
            self.write_to(destination, do_compress=do_compress)

    def __repr__(self):
        return 'LasData({}.{}, point fmt: {}, {} points, {} vlrs)'.format(
            self.header.version_major,
            self.header.version_minor,
            self.points_data.point_format_id,
            len(self.points_data),
            len(self.vlrs)
        )
