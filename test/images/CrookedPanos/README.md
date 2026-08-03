# 360° GPano Metadata Test Images

This directory contains equirectangular 360° test images prepared to address metadata parsing and orientation behaviors outlined in [Photo-Sphere-Viewer Issue #1786](https://github.com/mistic100/Photo-Sphere-Viewer/issues/1786).

The images:
  ThetaS\*.jpg: Lightly modified panorama images taken with a Ricoh Theta S camera.
  OverviewThetaS\*.jpg: Context photos of the Ricoh Theta S taken around the time the panoramas were recorded.
  CanonicalView.jpg: A reference example showing the intended corrected orientation.

## Metadata Modifications
For privacy and consistency across demonstrations, the following adjustments have been applied:
1. **Anonymization:** Anonymization: All original GPS coordinates, altitude values, and location metadata have been fully removed.
2. **Heading Normalization:** `XMP-GPano:PoseHeadingDegrees` has been uniformly offset across the image set so that 0° (North) aligns with the physical “North” marker visible in the scene. Note that the marker is not perfectly aligned with true north in reality.

Corrected views of these images should roughly satisfy the following:
  * The yellow tape representing the horizon should appear level (roll)
  * The yellow tape should be centered vertically (pitch)
  * The white "North" sign should be centered horizontally (heading)

The image "CanonicalView.jpg" illustrates these expected characteristics.

Because the roll, pitch, and heading are adjusted independently, these images *cannot* be used to determine the correct order of applying orientation adjustments.

## Usage Rights & License

These test assets are provided under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license. 

### You are free to:
* **Share & Adapt:** Copy, redistribute, remix, transform, and build upon these material for any purpose, including commercial use -- particularly for testing or improving panoramic rendering engines.

### Under the following terms:
* **Attribution:** You must give appropriate credit (e.g., naming Christopher Bruns), provide a link to the license, and indicate if changes were made. Attribution may be given in any reasonable manner, provided it does not imply endorsement.
* **No Warranties:** These assets are provided "as is", without warranty of any kind, express or implied. In no event shall the authors be liable for any claim, damages, or other liability.
