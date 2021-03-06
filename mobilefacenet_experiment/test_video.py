'''
    1. mtcnn: detect the face in the video and crop it for size=(112,112)
    2. mobilefacenet: recognize the detected face and predict the face name with max similarity in the collected face database.
'''
import cv2
import os
import numpy as np
import json
import time
from PIL import Image
import json
from tqdm import tqdm
# mtcnn
from mtcnn.detector import detect_faces
from mtcnn.models import PNet, RNet, ONet
# mobilefacenet
from backbone.model import MobileFacenet


import torch
import torch.nn as nn
import torch.backends.cudnn as cudnn
cudnn.benchmark = True

# device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# load mtcnn models
pnet = PNet().to(device)
rnet = RNet().to(device)
onet = ONet().to(device)

# load model
model = MobileFacenet()
test_model_path = '../pretrained_model/mobilefacenet/mobilefacenet.pth'
model.load_state_dict(torch.load(test_model_path))
model.eval()
model.to(device)

# id_name
id_name = json.load(open('./id_name.json', 'r')) # no use

def cosin_metric(x1, x2):
    return np.dot(x1, x2) / (np.linalg.norm(x1) * np.linalg.norm(x2))

def get_predict_name(feature):
    max_sim = -10
    pre_name = None
    for key in list(features_dict.keys()):
        sim = cosin_metric(feature, features_dict[key])
        if sim > max_sim:
            max_sim = sim
            pre_name = key
    print(pre_name, max_sim)
    if max_sim < 0.4:
        pre_name = 'unknown'
    return pre_name+' %.4f' % max_sim


def crop_face(img, bounding_boxes, facial_landmarks=[]):
    H, W = img.shape[0], img.shape[1]
    H_max = 0
    box = None

    for BOX in bounding_boxes:
        h2_h1 = int(BOX[3]) - int(BOX[1])
        if h2_h1 > H_max:
            box = BOX
            H_max = h2_h1

    h1, h2, w1, w2 = int(box[1]), int(box[3]), int(box[0]), int(box[2])

    if h2 - h1 < 60:
        print('face too small\n')
        return img

    # tune the h
    h1 = int(h1 - (h2 - h1) / 12)
    # check the boundary
    if h1 < 0:
        h1 = 0
    height = h2 - h1

    # tune the w
    w_middle = int((w2 + w1) / 2)
    w1 = int(w_middle - height / 2)
    if w1 < 0:
        w1 = 0
    elif w1 + height >= W:
        w1 = W - height - 1
    w2 = w1 + height

    face_img = img[h1:h2, w1:w2, :]
    face_img = cv2.resize(face_img, (112, 112))
    return face_img, box

def get_face_feature(model,face_img):
    face_img = face_img.astype(np.float32)
    face_img /= 255.0
    face_img -= (0.5, 0.5, 0.5)
    face_img /= (0.5, 0.5, 0.5)
    face_img = torch.from_numpy(face_img).float().permute(2, 0, 1).unsqueeze(0).to(device)
    with torch.no_grad():
        feature = model(face_img)
        feature = feature.squeeze().cpu().numpy()
        return feature

def get_your_faceImg_feature(name, model, features_dict):
    faceImg_path = './video/your_face_img'
    num_img_useful = 0
    for idx, img_name in enumerate(os.listdir(faceImg_path)):
        # detect face in your img
        img = Image.open(faceImg_path + '/' + img_name).convert('RGB')
        try:
            bounding_boxes, landmarks = detect_faces(img, pnet=pnet, rnet=rnet, onet=onet, device=device)
        except:
            continue
        if len(bounding_boxes) == 0:
            continue
        # crop the face from the img (112, 112)
        face_img, box = crop_face(np.array(img), bounding_boxes, landmarks)
        feature = get_face_feature(model, face_img)
        features_dict[name+'_'+str(idx)] = feature
        num_img_useful += 1
    print('Successfully collected your face img for %ds ' % num_img_useful)
    return features_dict



if __name__ == '__main__':
    features_dict = json.load(open('../pretrained_model/mobilefacenet/features_dict/lab_undergraduate_visible_features.json', 'r'))
    test_your_video = True # 使用自己的照片测试，需要在video放入你的视频并设置测试视频设置为你的视频，同时在video/your_faceImg文件夹中放入你的图片，用于比对和识别：数量10+，
    if test_your_video == True:
        name = 'your name'
        features_dict = get_your_faceImg_feature(name, model, features_dict)
    print('Features length:', len(features_dict))
    # select one data source from the follow optional img sources entrance
    # 拍视频尽量避免光线影响，不要太亮，摄像头距离人脸1米左右
    video_src = './video/zengzhiwei.mp4' # video path
    # video_src = 0 # camera device id
    capture = cv2.VideoCapture(video_src)
    if not capture.isOpened():
        print('Camera is not opened or the video src doesnt exit!')
    else:
        idx_frame = 0
        while True:
            ret, frame = capture.read()
            idx_frame += 1
            if idx_frame % 8 != 0:  # 每8帧预测一次
                continue
            idx_frame = 0
            # cv2.imshow('Frame', frame)
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # frame = cv2.resize(frame, dsize=(0,0), fx=0.5,fy=0.5)
            # detect the face in the img
            img = Image.fromarray(frame)
            try:
                bounding_boxes, landmarks = detect_faces(img, pnet=pnet, rnet=rnet, onet=onet, device=device)
            except:
                continue
            if len(bounding_boxes) ==0:
                continue
            # crop the face from the img
            face_img, box = crop_face(frame, bounding_boxes, landmarks)
            cv2.imshow('face', face_img)
            # recognize who is the detected face
            feature = get_face_feature(model, face_img)
            # select the most similar person from the collected face database
            pre_name = get_predict_name(feature)
            # put the result in the img
            cv2.putText(frame, pre_name, (20, 40), 0, 1, (0, 255, 0), 2)
            cv2.rectangle(frame, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (255, 255, 255), 2)
            cv2.imshow('Prediction', frame)
            cv2.waitKey(1)

    capture.release()
