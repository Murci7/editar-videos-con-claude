"""Cut a person out of a photo with Apple Vision (person segmentation, accurate) → PNG with alpha.

macOS only (Apple Vision). Runs with a PyObjC venv:  ~/.cache/editar-videos-vision/bin/python cutout.py input.png output.png
(create it once: python3 -m venv ~/.cache/editar-videos-vision && ~/.cache/editar-videos-vision/bin/pip install
pyobjc-framework-Vision pyobjc-framework-Quartz)
"""
import sys
import Quartz
import Vision
from Foundation import NSURL

src_url = NSURL.fileURLWithPath_(sys.argv[1])
ci = Quartz.CIImage.imageWithContentsOfURL_(src_url)
req = Vision.VNGeneratePersonSegmentationRequest.alloc().initWithCompletionHandler_(None)
req.setQualityLevel_(Vision.VNGeneratePersonSegmentationRequestQualityLevelAccurate)
req.setOutputPixelFormat_(1278226488)  # kCVPixelFormatType_OneComponent8 ('L008')
handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci, {})
ok, err = handler.performRequests_error_([req], None)
if not ok or not req.results():
    sys.exit(f"segmentation failed: {err}")
mask = Quartz.CIImage.imageWithCVPixelBuffer_(req.results()[0].pixelBuffer())
ext, mext = ci.extent(), mask.extent()
mask = mask.imageByApplyingTransform_(Quartz.CGAffineTransformMakeScale(ext.size.width / mext.size.width,
                                                                        ext.size.height / mext.size.height))
blend = Quartz.CIFilter.filterWithName_("CIBlendWithMask")
blend.setValue_forKey_(ci, "inputImage")
blend.setValue_forKey_(Quartz.CIImage.imageWithColor_(Quartz.CIColor.clearColor()).imageByCroppingToRect_(ext), "inputBackgroundImage")
blend.setValue_forKey_(mask, "inputMaskImage")
ctx = Quartz.CIContext.contextWithOptions_(None)
cs = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
ok, err = ctx.writePNGRepresentationOfImage_toURL_format_colorSpace_options_error_(
    blend.outputImage(), NSURL.fileURLWithPath_(sys.argv[2]), Quartz.kCIFormatRGBA8, cs, {}, None)
print("ok" if ok else f"error {err}", sys.argv[2])
