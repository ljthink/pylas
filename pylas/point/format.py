from . import dims
from .. import errors


class PointFormat:
    def __init__(self, point_format_id, extra_dims=None):
        self.id = point_format_id
        if extra_dims is None:
            extra_dims = []
        self.extra_dims = extra_dims

    @property
    def dimension_names(self):
        return self.unpacked_dtype.names

    @property
    def dtype(self):
        dtype = self._access_dict(dims.ALL_POINT_FORMATS_DTYPE, self.id)
        dtype = self._dtype_add_extra_dims(dtype)
        return dtype

    @property
    def unpacked_dtype(self):
        dtype = self._access_dict(dims.UNPACKED_POINT_FORMATS_DTYPES, self.id)
        dtype = self._dtype_add_extra_dims(dtype)
        return dtype

    @property
    def composed_fields(self):
        return self._access_dict(dims.COMPOSED_FIELDS, self.id)

    @property
    def sub_fields(self):
        sub_fields_dict = {}
        for composed_dim_name, sub_fields in self.composed_fields.items():
            for sub_field in sub_fields:
                sub_fields_dict[sub_field.name] = (composed_dim_name, sub_field)
        return sub_fields_dict

    @property
    def extra_dimension_names(self):
        return [extd[0] for extd in self.extra_dims]

    @property
    def num_extra_bytes(self):
        return sum(extra_dim[1] for extra_dim in self.extra_dims)

    @property
    def has_waveform_packet(self):
        dimensions = set(self.dimension_names)
        return all(name in dimensions for name in dims.WAVEFORM_FIELDS_NAMES)

    @staticmethod
    def _access_dict(d, key):
        try:
            return d[key]
        except KeyError as e:
            raise errors.PointFormatNotSupported(e)

    def _dtype_add_extra_dims(self, dtype):
        if self.extra_dims is not None:
            dtype = dims.dtype_append(dtype, self.extra_dims)
        return dtype

    def __int__(self):
        return self.id

    # def __str__(self):
    #     return str(self.id)

    def __repr__(self):
        return "<PointFormat({})>".format(self.id)


def lost_dimensions(point_fmt_in, point_fmt_out):
    """  Returns a list of the names of the dimensions that will be lost
    when converting from point_fmt_in to point_fmt_out
    """

    unpacked_dims_in = PointFormat(point_fmt_in).dtype
    unpacked_dims_out = PointFormat(point_fmt_out).dtype

    out_dims = unpacked_dims_out.fields
    completely_lost = []
    for dim_name in unpacked_dims_in.names:
        if dim_name not in out_dims:
            completely_lost.append(dim_name)
    return completely_lost
