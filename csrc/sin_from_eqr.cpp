/*
 *  Convert equirectangular image to sinusoidal.
 *  One scan line at a time.
 *  using cache-coherent latitude-aware order(n) downsampling
 *  output pixels in the invalid region will be a mirror of the central valid
 *  region near the valid region, and a blend of the extreme edge values elsewhere
 *  in-place conversion possible by setting src and dst to the same value
/* */

#include <algorithm>
#include <cmath>
#include <numbers>
#include <vector>

// Macro to handle cross-platform DLL/Shared Library exports
#if defined(_WIN32) || defined(__CYGWIN__)
#define EXPORT_API __declspec(dllexport)
#else
#define EXPORT_API __attribute__((visibility("default")))
#endif

using SUM_TYPE = std::int64_t;  // wide type to avoid overflow of accumulated pixel values

template<typename PIXEL_TYPE>  // expected types uint8_t, uint16_t for now
void sin_from_equi(const PIXEL_TYPE* src, PIXEL_TYPE* dst, size_t nRows, size_t nCols, size_t nChans)
{
    // 1) allocate a buffer scan line
    std::vector<PIXEL_TYPE> scan_buffer(nCols * nChans);
    // use 64-bit ints to accumulate the blended sum running total to avoid overflow
    std::vector<SUM_TYPE> pixelSum(nChans);
    // 2) loop over scan lines
	for(size_t row = 0; row < nRows; row++) 
    {
        std::ranges::fill(scan_buffer, PIXEL_TYPE{ 0 });

        auto latitude = -std::numbers::pi * ((0.5 + row) / nRows - 0.5);  // range (-PI/2, +PI/2)
        // clamp to +- (pi - epsilon)
        latitude = std::max(-std::numbers::pi/2.0 + 1e-6, latitude);
        latitude = std::min(std::numbers::pi/2.0 - 1e-6, latitude);
        auto clat = cos(latitude);

        // TODO: loop over output pixels
        auto c = (nCols - 1)/2.0;  // center of scan line in pixel indices
        int min_src_px = 0;  // c - c;
        // auto max_src_px = nCols - 1;  // c + c;
        int min_dst_px = int(std::floor(c - c * clat));
        int max_dst_px = int(std::ceil(c + c * clat));
        int src0 = min_src_px;
        int src1 = src0;
        auto sp = &src[row * nCols * nChans];  // pointer to beginning of source scan line
        for (auto dpx = min_dst_px; dpx <= max_dst_px; ++dpx) {
            // lower bound on source pixels src0 is already set
            // upper bound src1 is half way to the next destination pixel
            src1 = int(std::round(c + (dpx - c) / clat));
            std::ranges::fill(pixelSum, 0);

            // debug
            if (row == nRows - 1 && dpx == max_dst_px) {
                // scan_buffer[nChans * dpx + chan] = PIXEL_TYPE(10);
                int x = 3;
            }

            for (auto spx = src0; spx <= src1; ++spx) {
                for (auto chan = 0; chan < nChans; ++chan) {
                    pixelSum[chan] += sp[spx];
                }
            }
            // normalize rgb values and write to scanline buffer
            auto count = src1 - src0 + 1.0f;
            for (auto chan = 0; chan < nChans; ++chan) {
                auto intensity = std::round(pixelSum[chan] / count);
                scan_buffer[nChans * dpx + chan] = PIXEL_TYPE(intensity);
            }


            src0 = src1 + 1;  // update for next iteration; each source pixel goes to exactly one destination pixel
        }

        // TODO: write mirror pixels at boundaries

        // copy the buffer scan line to the destination
        std::copy(scan_buffer.begin(), scan_buffer.end(), dst + row * nCols * nChans);
    }
}

// Explicit C-compatible wrappers
extern "C" {

    EXPORT_API void sin_from_equi_u8(const uint8_t* src, uint8_t* dst, size_t nRows, size_t nCols, size_t nChans) {
        sin_from_equi<uint8_t>(src, dst, nRows, nCols, nChans);
    }

    EXPORT_API void sin_from_equi_u16(const uint16_t* src, uint16_t* dst, size_t nRows, size_t nCols, size_t nChans) {
        sin_from_equi<uint16_t>(src, dst, nRows, nCols, nChans);
    }

}
