# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A demo which runs object detection on camera frames.

export TEST_DATA=/usr/lib/python3/dist-packages/edgetpu/test_data

Run face detection model:
python3 -m edgetpuvision.detect \
  --model ${TEST_DATA}/mobilenet_ssd_v2_face_quant_postprocess_edgetpu.tflite

Run coco model:
python3 -m edgetpuvision.detect \
  --model ${TEST_DATA}/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite \
  --labels ${TEST_DATA}/coco_labels.txt
"""
import argparse
import time
import re
import os
import logging
from edgetpu.detection.engine import DetectionEngine
import ambianic
from ambianic.cameras.gstreamer import InputStreamProcessor

log = logging.getLogger(__name__)


def load_labels(path):
    p = re.compile(r'\s*(\d+)(.+)')
    with open(path, 'r', encoding='utf-8') as f:
       lines = (p.match(line).groups() for line in f.readlines())
       return {int(num): text.strip() for num, text in lines}

def shadow_text(dwg, x, y, text, font_size=20):
    dwg.add(dwg.text(text, insert=(x+1, y+1), fill='black', font_size=font_size))
    dwg.add(dwg.text(text, insert=(x, y), fill='white', font_size=font_size))

def generate_svg(dwg, objs, labels, text_lines):
    width, height = dwg.attribs['width'], dwg.attribs['height']
    for y, line in enumerate(text_lines):
        shadow_text(dwg, 10, y*20, line)
    for obj in objs:
        x0, y0, x1, y1 = obj.bounding_box.flatten().tolist()
        x, y, w, h = x0, y0, x1 - x0, y1 - y0
        x, y, w, h = int(x * width), int(y * height), int(w * width), int(h * height)
        percent = int(100 * obj.score)
        label = '%d%% %s' % (percent, labels[obj.label_id])
        shadow_text(dwg, x, y - 5, label)
        dwg.add(dwg.rect(insert=(x,y), size=(w, h),
                        fill='red', fill_opacity=0.3, stroke='white'))
        #print("SVG canvas width: {w}, height: {h}".format(w=width,h=height))
        #dwg.add(dwg.rect(insert=(0,0), size=(width, height),
        #                fill='green', fill_opacity=0.2, stroke='white'))

class CameraStreamProcessor():

    def __init__(self):
        self.input_proc = None

    def start(self):
        log.info("Starting %s ", self.__class__.__name__)
        default_model_dir = ambianic.AI_MODELS_DIR
        default_model = 'mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite'
        default_labels = 'coco_labels.txt'
        parser = argparse.ArgumentParser()
        parser.add_argument('--model', help='.tflite model path',
                            default=os.path.join(default_model_dir,default_model))
        parser.add_argument('--labels', help='label file path',
                            default=os.path.join(default_model_dir, default_labels))
        parser.add_argument('--top_k', type=int, default=3,
                            help='number of classes with highest score to display')
        parser.add_argument('--threshold', type=float, default=0.2,
                            help='class score threshold')
        args = parser.parse_args()

        print("Loading %s with %s labels."%(args.model, args.labels))
        engine = DetectionEngine(args.model)
        labels = load_labels(args.labels)

        last_time = time.monotonic()

        def inference_callback(image, svg_canvas):
          nonlocal last_time
          start_time = time.monotonic()
          objs = engine.DetectWithImage(image, threshold=args.threshold,
                                        keep_aspect_ratio=True, relative_coord=True,
                                        top_k=args.top_k)
          end_time = time.monotonic()
          inf_time = (end_time - start_time) * 1000
          fps = 1.0/(end_time - last_time)
          log.info('Inference: %.2f ms  FPS: %.2f fps', inf_time, fps)
          last_time = end_time
          generate_svg(svg_canvas, objs, labels, text_lines)

        self.input_proc = InputStreamProcessor(inference_callback)
        result = self.input_proc.run_pipeline()
        log.info("Stopped %s", self.__class__.__name__)

    def stop(self):
        log.info("Stopping %s", self.__class__.__name__)
        self.input_proc.stop_pipeline()
