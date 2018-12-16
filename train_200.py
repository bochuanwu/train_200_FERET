# -*- coding: utf-8 -*-
"""
Created on Wed Dec  5 11:14:53 2018

@author: 16703
"""
import pandas as pd
import cv2
import numpy as np
from keras import layers
from keras.layers import Input,Dense,Activation,ZeroPadding2D,\
    BatchNormalization,Flatten,Conv2D,AveragePooling2D,MaxPooling2D
import os
import keras
from keras.models import Model
import keras.backend as K
K.set_image_data_format("channels_last")
K.set_learning_phase(1)
from keras.callbacks import ModelCheckpoint
seed = 7
np.random.seed(seed)
from keras.callbacks import ReduceLROnPlateau
from keras.initializers import glorot_uniform



img_width, img_height = 80, 80

train_data_dir = './train/'
nb_epoch = 20

#恒等模块——identity_block
def identity_block(X,f,filters,stage,block):
    """
    三层的恒等残差块
    param :
    X -- 输入的张量，维度为（m, n_H_prev, n_W_prev, n_C_prev）
    f -- 整数，指定主路径的中间 CONV 窗口的形状
    filters -- python整数列表，定义主路径的CONV层中的过滤器数目
    stage -- 整数，用于命名层，取决于它们在网络中的位置
    block --字符串/字符，用于命名层，取决于它们在网络中的位置
    return:
    X -- 三层的恒等残差块的输出，维度为：(n_H, n_W, n_C)
    """
    #定义基本的名字
    conv_name_base = "res"+str(stage)+block+"_branch"
    bn_name_base = "bn"+str(stage)+block+"_branch"
 
    #过滤器
    F1,F2,F3 = filters
 
    #保存输入值,后面将需要添加回主路径
    X_shortcut = X
 
    #主路径第一部分
    X = Conv2D(filters=F1,kernel_size=(1,1),strides=(1,1),padding="valid",
               name=conv_name_base+"2a",kernel_initializer=glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis=3,name=bn_name_base+"2a")(X)
    X = Activation("relu")(X)
 
    # 主路径第二部分
    X = Conv2D(filters=F2,kernel_size=(f,f),strides=(1,1),padding="same",
               name=conv_name_base+"2b",kernel_initializer=glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis=3,name=bn_name_base+"2b")(X)
    X = Activation("relu")(X)
 
    # 主路径第三部分
    X = Conv2D(filters=F3,kernel_size=(1,1),strides=(1,1),padding="valid",
               name=conv_name_base+"2c",kernel_initializer=glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis=3,name=bn_name_base+"2c")(X)
 
    # 主路径最后部分,为主路径添加shortcut并通过relu激活
    X = layers.add([X,X_shortcut])
    X = Activation("relu")(X)
 
    return X
 
#卷积残差块——convolutional_block
def convolutional_block(X,f,filters,stage,block,s=2):
    """
    param :
    X -- 输入的张量，维度为（m, n_H_prev, n_W_prev, n_C_prev）
    f -- 整数，指定主路径的中间 CONV 窗口的形状（过滤器大小，ResNet中f=3）
    filters -- python整数列表，定义主路径的CONV层中过滤器的数目
    stage -- 整数，用于命名层，取决于它们在网络中的位置
    block --字符串/字符，用于命名层，取决于它们在网络中的位置
    s -- 整数，指定使用的步幅
    return:
    X -- 卷积残差块的输出，维度为：(n_H, n_W, n_C)
    """
    # 定义基本的名字
    conv_name_base = "res" + str(stage) + block + "_branch"
    bn_name_base = "bn" + str(stage) + block + "_branch"
 
    # 过滤器
    F1, F2, F3 = filters
 
    # 保存输入值,后面将需要添加回主路径
    X_shortcut = X
 
    # 主路径第一部分
    X = Conv2D(filters=F1, kernel_size=(1, 1), strides=(s, s), padding="valid",
               name=conv_name_base + "2a", kernel_initializer=glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis=3, name=bn_name_base + "2a")(X)
    X = Activation("relu")(X)
 
    # 主路径第二部分
    X = Conv2D(filters=F2, kernel_size=(f, f), strides=(1, 1), padding="same",
               name=conv_name_base + "2b", kernel_initializer=glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis=3, name=bn_name_base + "2b")(X)
    X = Activation("relu")(X)
 
    # 主路径第三部分
    X = Conv2D(filters=F3, kernel_size=(1, 1), strides=(1, 1), padding="valid",
               name=conv_name_base + "2c", kernel_initializer=glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis=3, name=bn_name_base + "2c")(X)
 
    #shortcut路径
    X_shortcut = Conv2D(filters=F3,kernel_size=(1,1),strides=(s,s),padding="valid",
               name=conv_name_base+"1",kernel_initializer=glorot_uniform(seed=0))(X_shortcut)
    X_shortcut = BatchNormalization(axis=3,name=bn_name_base+"1")(X_shortcut)
 
    # 主路径最后部分,为主路径添加shortcut并通过relu激活
    X = layers.add([X, X_shortcut])
    X = Activation("relu")(X)
 
    return X
 
#50层ResNet模型构建
def ResNet50(input_shape = (229,229,3),classes = 61):
    """
    构建50层的ResNet,结构为：
    CONV2D -> BATCHNORM -> RELU -> MAXPOOL -> CONVBLOCK -> IDBLOCK*2 -> CONVBLOCK -> IDBLOCK*3
    -> CONVBLOCK -> IDBLOCK*5 -> CONVBLOCK -> IDBLOCK*2 -> AVGPOOL -> TOPLAYER
    param :
    input_shape -- 数据集图片的维度
    classes -- 整数，分类的数目
    return:
    model -- Keras中的模型实例
    """
    #将输入定义为维度大小为 input_shape的张量
    X_input = Input(input_shape)
 
    # Zero-Padding
    X = ZeroPadding2D((3,3))(X_input)
 
    # Stage 1
    X = Conv2D(64,kernel_size=(5,5),strides=(2,2),name="conv1",kernel_initializer=glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis=3,name="bn_conv1")(X)
    X = Activation("relu")(X)
    X = MaxPooling2D(pool_size=(3,3),strides=(2,2))(X)
 
    # Stage 2
    X = convolutional_block(X,f=3,filters=[64,64,256],stage=2,block="a",s=1)
    X = identity_block(X,f=3,filters=[64,64,256],stage=2,block="b")
    X = identity_block(X,f=3,filters=[64,64,256],stage=2,block="c")
 
    #Stage 3
    X = convolutional_block(X,f=3,filters=[128,128,512],stage=3,block="a",s=2)
    X = identity_block(X,f=3,filters=[128,128,512],stage=3,block="b")
    X = identity_block(X,f=3,filters=[128,128,512],stage=3,block="c")
    X = identity_block(X,f=3,filters=[128,128,512],stage=3,block="d")
 
    # Stage 4
    X = convolutional_block(X,f=3,filters=[256,256,1024],stage=4,block="a",s=2)
    X = identity_block(X,f=3,filters=[256,256,1024],stage=4,block="b")
    X = identity_block(X,f=3,filters=[256,256,1024],stage=4,block="c")
    X = identity_block(X,f=3,filters=[256,256,1024],stage=4,block="d")
    X = identity_block(X,f=3,filters=[256,256,1024],stage=4,block="e")
    X = identity_block(X,f=3,filters=[256,256,1024],stage=4,block="f")
 
    #Stage 5
    X = convolutional_block(X,f=3,filters=[512,512,2048],stage=5,block="a",s=2)
    X = identity_block(X,f=3,filters=[256,256,2048],stage=5,block="b")
    X = identity_block(X,f=3,filters=[256,256,2048],stage=5,block="c")
 
    #最后阶段
    #平均池化
    X = AveragePooling2D(pool_size=(2,2))(X)
 
    #输出层
    X = Flatten()(X)
    X = Dense(classes, activation='softmax', name='fc61')(X)
 
    #创建模型
    model = Model(inputs=X_input,outputs=X,name="ResNet50")
 
    return model
 
#运行构建的模型图
model = ResNet50(input_shape=(img_width,img_height,3),classes=200)
Adam=keras.optimizers.Adam(lr=0.0001)
learning_rate_reduction = ReduceLROnPlateau(monitor='val_acc', patience=2, verbose=1, factor=0.1, min_lr=0.00000001)
model.compile(optimizer=Adam, loss='categorical_crossentropy',metrics=['accuracy'])

#加载数据集
img_path=[]
def loadpath(input_dir):
    for (path, dirnames, filenames) in os.walk(input_dir):
        for dirname in dirnames:
            img_path.append(path+'/'+dirname)
        return img_path

path= loadpath(train_data_dir)
imgs=[]
labs=[]
def readData(paths):
    for path in paths:
        for filename in os.listdir(path):
            if filename.endswith('.tif'):
                filename = path + '/' + filename
                print(filename)
                img = cv2.imread(filename)
                imgs.append(img)
                labs.append(path)

                
#数据录入处理
readData(path)
for lab in labs:
    for i in range(len(path)):
        if lab ==  path[i]:
            lab=i+1
       
imgs = np.array(imgs)
print(imgs)
data_dummy=pd.get_dummies(labs)
labs = np.array(data_dummy)
# 随机划分测试集与训练集
size=80
import random
from sklearn.model_selection import train_test_split
train_x,test_x,train_y,test_y = train_test_split(imgs, labs, test_size=0.001, random_state=random.randint(0,100))
# 参数：图片数据的总数，图片的高、宽、通道
train_x = train_x.reshape(train_x.shape[0], size, size, 3)

test_x = test_x.reshape(test_x.shape[0], size, size, 3)
# 将数据转换成小于1的数
train_x = train_x.astype('float32')/255.0
test_x = test_x.astype('float32')/255.0
print('train size:%s, test size:%s' % (len(train_x), len(test_x)))

checkpoint = ModelCheckpoint('weights.hdf5', monitor='val_acc', verbose=1, save_best_only=True, mode='max', period=1)
#训练模型
model.fit(train_x, train_y, epochs=50, batch_size=25,callbacks=[checkpoint,learning_rate_reduction])
#model.fit_generator(data_generator(path,labs,batch_size),samples_per_epoch=len(labs)//20,nb_epoch=20,validation_data=data_generator(path,labs,batch_size),nb_val_samples=len(labs)//20,callbacks=[checkpoint,learning_rate_reduction])
#model.fit_generator(data_generator(trian_img_paths,train_labels,batch_size),samples_per_epoch=len(train_labels)//32,nb_epoch=10,validation_data=data_generator(trian_img_paths1,train_labels1,batch_size),nb_val_samples=len(train_labels1)//32,callbacks=[checkpoint])
model.save(os.path.join('./', 'my_model_resnet.h5'))
