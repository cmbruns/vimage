"""
Experimental code to make pythonic interface to low level libjpeg

Following example in
https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/example.c
"""

import ctypes
from ctypes import byref, c_int, c_size_t, cdll, CFUNCTYPE, POINTER, sizeof, Structure

JPEG_LIB_VERSION = 62
turbo_jpeg_lib = cdll.LoadLibrary("C:/libjpeg-turbo64/bin/jpeg62.dll")

DCTSIZE2 = 64  # DCTSIZE squared; num of elements in a block
NUM_QUANT_TBLS = 4  # Quantization tables are numbered 0..3
NUM_HUFF_TBLS = 4   # Huffman tables are numbered 0..3
NUM_ARITH_TBLS = 16  # Arith-coding tables are numbered 0..15
MAX_COMPS_IN_SCAN = 4  # JPEG limit on num of components in one scan
D_MAX_BLOCKS_IN_MCU = 10  # decompressor's limit on blocks per MCU

JDIMENSION = ctypes.c_uint
JOCTET = ctypes.c_ubyte

boolean = ctypes.c_ubyte
# Representation of a single sample (pixel element value). defined in `jmorecfg.h`
JSAMPLE = ctypes.c_ubyte

#  defined in `jpeglib.h`
# ptr to one image row of pixel samples.
JSAMPROW = ctypes.POINTER(JSAMPLE)
# ptr to some rows (a 2-D sample array).
JSAMPARRAY = ctypes.POINTER(JSAMPROW)


class JQUANT_TBL(ctypes.Structure):
    '''
    DCT coefficient quantization tables.
    '''
    _fields_ = (
        ('quantval', ctypes.c_uint16 * DCTSIZE2),
        ('sent_table', boolean),
    )


class JHUFF_TBL(ctypes.Structure):
    '''
    Huffman coding tables.
    '''
    _fields_ = (
        ('bits', ctypes.c_uint8 * 17),
        ('huffval', ctypes.c_uint8 * 256),
        ('sent_table', boolean),
    )


class jpeg_component_info(ctypes.Structure):
    '''
    Basic info about one component (color channel).
    '''
    _fields_ = (
        ('component_id', ctypes.c_int),
        ('component_index', ctypes.c_int),
        ('h_samp_factor', ctypes.c_int),
        ('v_samp_factor', ctypes.c_int),
        ('quant_tbl_no', ctypes.c_int),
        ('dc_tbl_no', ctypes.c_int),
        ('ac_tbl_no', ctypes.c_int),
        ('width_in_blocks', JDIMENSION),
        ('height_in_blocks', JDIMENSION),
        # ('DCT_h_scaled_size', ctypes.c_int),  # if JPEG_LIB_VERSION >= 70
        # ('DCT_v_scaled_size', ctypes.c_int),  # if JPEG_LIB_VERSION >= 70
        ('DCT_scaled_size', ctypes.c_int),  # if JPEG_LIB_VERSION < 70
        ('downsampled_width', JDIMENSION),
        ('downsampled_height', JDIMENSION),
        ('component_needed', boolean),
        ('MCU_width', ctypes.c_int),
        ('MCU_height', ctypes.c_int),
        ('MCU_blocks', ctypes.c_int),
        ('MCU_sample_width', ctypes.c_int),
        ('last_col_width', ctypes.c_int),
        ('last_row_height', ctypes.c_int),
        ('quant_table', ctypes.POINTER(JQUANT_TBL)),
        ('dct_table', ctypes.c_void_p),
    )


class jpeg_error_mgr(Structure):
    pass


class jpeg_memory_mgr(Structure):
    pass


class jpeg_progress_monitor(Structure):
    pass


class jpeg_decompress_struct(Structure):  # incomplete type / forward declaration
    pass


j_decompress_ptr = ctypes.POINTER(jpeg_decompress_struct)

# Function pointer types for jpeg_src_mgr
pfn_init_source = CFUNCTYPE(None, j_decompress_ptr)
pfn_fill_input_buffer = CFUNCTYPE(boolean, j_decompress_ptr)
pfn_skip_input_data = CFUNCTYPE(None, j_decompress_ptr, ctypes.c_long)
pfn_resync_to_restart = CFUNCTYPE(boolean, j_decompress_ptr, ctypes.c_int)
pfn_term_source = CFUNCTYPE(None, j_decompress_ptr)


class jpeg_source_mgr(Structure):
    _fields_ = (
        ("next_input_byte", POINTER(JOCTET)), # => next byte to read from buffer */
        ("bytes_in_buffer", ctypes.c_size_t ),       # number of bytes remaining in buffer */

        ("init_source", pfn_init_source),
        ("fill_input_buffer", pfn_fill_input_buffer),
        ("skip_input_data", pfn_skip_input_data),
        ("resync_to_restart", pfn_resync_to_restart),
        ("term_source", pfn_term_source),
    )


jpeg_decompress_struct._fields_ = (
        # jpeg_common_fields
        ('err', ctypes.POINTER(jpeg_error_mgr)),  # offset 0
        ('mem', ctypes.POINTER(jpeg_memory_mgr)),
        ('progress', ctypes.POINTER(jpeg_progress_monitor)),
        ('client_data', ctypes.c_void_p),
        ('is_decompressor', boolean),
        ('global_state', ctypes.c_int),  # offset 36

        ('src', ctypes.POINTER(jpeg_source_mgr)),  # offset: 40

        ('image_width', JDIMENSION),
        ('image_height', JDIMENSION),
        ('num_components', ctypes.c_int),
        ('jpeg_color_space', ctypes.c_int),

        ('out_color_space', ctypes.c_int),  # offset: 64
        ('scale_num', ctypes.c_uint),
        ('scale_denom', ctypes.c_uint),  # offset: 72

        ('output_gamma', ctypes.c_double),

        ('buffered_image', boolean),  # offset: 88
        ('raw_data_out', boolean),  # offset: 89

        ('dct_method', ctypes.c_int),  # offset: 92
        ('do_fancy_upsampling', boolean),  # offset: 96
        ('do_block_smoothing', boolean),

        ('quantize_colors', boolean),  # offset: 98

        ('dither_mode', ctypes.c_int),
        ('two_pass_quantize', boolean),
        ('desired_number_of_colors', ctypes.c_int),  # offset: 108

        ('enable_1pass_quant', boolean),  # offset: 112
        ('enable_external_quant', boolean),
        ('enable_2pass_quant', boolean),

        ('output_width', JDIMENSION),  # offset: 116
        ('output_height', JDIMENSION),
        ('out_color_components', ctypes.c_int),
        ('output_components', ctypes.c_int),

        ('rec_outbuf_height', ctypes.c_int),

        ('actual_number_of_colors', ctypes.c_int),  # 136
        ('colormap', JSAMPARRAY),

        ('output_scanline', JDIMENSION),

        ('input_scan_number', ctypes.c_int),
        ('input_iMCU_row', JDIMENSION),  # offset: 160

        ('output_scan_number', ctypes.c_int),
        ('output_iMCU_row', JDIMENSION),

        ('coef_bits', ctypes.c_void_p),

        ('quant_tbl_ptrs', ctypes.POINTER(JQUANT_TBL) * NUM_QUANT_TBLS),

        ('dc_huff_tbl_ptrs', ctypes.POINTER(JHUFF_TBL) * NUM_HUFF_TBLS),
        ('ac_huff_tbl_ptrs', ctypes.POINTER(JHUFF_TBL) * NUM_HUFF_TBLS),

        ('data_precision', ctypes.c_int),

        ('comp_info', ctypes.POINTER(jpeg_component_info)),

        # ('is_baseline', boolean),  # JPEG_LIB_VERSION >= 80
        ('progressive_mode', boolean),
        ('arith_code', boolean),

        ('arith_dc_L', ctypes.c_uint8 * NUM_ARITH_TBLS),
        ('arith_dc_U', ctypes.c_uint8 * NUM_ARITH_TBLS),
        ('arith_ac_K', ctypes.c_uint8 * NUM_ARITH_TBLS),

        ('restart_interval', ctypes.c_uint),

        ('saw_JFIF_marker', boolean),  # 352

        ('JFIF_major_version', ctypes.c_uint8),
        ('JFIF_minor_version', ctypes.c_uint8),
        ('density_unit', ctypes.c_uint8),
        ('X_density', ctypes.c_uint16),
        ('Y_density', ctypes.c_uint16),
        ('saw_Adobe_marker', boolean),
        ('Adobe_transform', ctypes.c_uint8),

        # added by libjpeg-9, Color transform identifier derived from LSE marker, otherwise zero
        # ('color_transform', ctypes.c_int),

        ('CCIR601_sampling', boolean),

        ('marker_list', ctypes.c_void_p),

        ('max_h_samp_factor', ctypes.c_int),
        ('max_v_samp_factor', ctypes.c_int),

        # ('min_DCT_h_scaled_size', ctypes.c_int),  # if JPEG_LIB_VERSION >= 70
        # ('min_DCT_v_scaled_size', ctypes.c_int),  # if JPEG_LIB_VERSION >= 70
        ('min_DCT_scaled_size', ctypes.c_int),  # if JPEG_LIB_VERSION < 70

        ('total_iMCU_rows', JDIMENSION),

        ('sample_range_limit', ctypes.c_void_p),  # offset: 392

        ('comps_in_scan', ctypes.c_int),

        ('cur_comp_info', ctypes.POINTER(jpeg_component_info) * MAX_COMPS_IN_SCAN),

        ('MCUs_per_row', JDIMENSION),
        ('MCU_rows_in_scan', JDIMENSION),

        ('blocks_in_MCU', ctypes.c_int),
        ('MCU_membership', ctypes.c_int * D_MAX_BLOCKS_IN_MCU),

        ('Ss', ctypes.c_int),  # offset: 492
        ('Se', ctypes.c_int),
        ('Ah', ctypes.c_int),
        ('Al', ctypes.c_int),

        # if JPEG_LIB_VERSION >= 80
        # ('block_size', ctypes.c_int),
        # ('natural_order', ctypes.POINTER(ctypes.c_int)),
        # ('lim_Se', ctypes.c_int),

        ('unread_marker', ctypes.c_int),

        ('master', ctypes.c_void_p),
        ('main', ctypes.c_void_p),
        ('coef', ctypes.c_void_p),
        ('post', ctypes.c_void_p),
        ('inputctl', ctypes.c_void_p),
        ('marker', ctypes.c_void_p),
        ('entropy', ctypes.c_void_p),
        ('idct', ctypes.c_void_p),
        ('upsample', ctypes.c_void_p),
        ('cconvert', ctypes.c_void_p),
        ('cquantize', ctypes.c_void_p),  # offset: 592
    )

print(ctypes.sizeof(jpeg_decompress_struct))
for f, t in jpeg_decompress_struct._fields_:
    a = getattr(jpeg_decompress_struct, f)
    print(f, a)

jpeg_create_decompress = turbo_jpeg_lib.jpeg_CreateDecompress
jpeg_create_decompress.restype = None
jpeg_create_decompress.argtypes = [POINTER(jpeg_decompress_struct), c_int, c_size_t]


def main():
    print("Hello")
    c_info = jpeg_decompress_struct()
    jpeg_create_decompress(byref(c_info), JPEG_LIB_VERSION, sizeof(jpeg_decompress_struct))


if __name__ == "__main__":
    main()
