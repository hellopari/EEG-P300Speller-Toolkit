# -*- coding: utf-8 -*-

import numpy as np
from common.datawrapper import *
from common.ButterWorth_filter import *
from scipy.stats import zscore


def load_traindata(filepath, filter):
    data = read_matdata(filepath, ['Signal', 'Flashing', 'StimulusCode', 'TargetChar'])
    signal = data['Signal']
    flashing = data['Flashing']
    stimuluscode = data['StimulusCode']
    targetchar = data['TargetChar'][0]
    return extract_eegdata(signal, flashing, stimuluscode, targetchar, filter)


def load_testdata(filepath, labelpath, filter):
    data = read_matdata(filepath, ['Signal', 'Flashing', 'StimulusCode'])
    signal = data['Signal']
    flashing = data['Flashing']
    stimuluscode = data['StimulusCode']
    with open(labelpath, 'r') as myfile:
        targetchar = myfile.read().replace('\n', '')
        # 去掉换行和空格
    return extract_eegdata(signal, flashing, stimuluscode, targetchar, filter)


def extract_eegdata(signal, flashing, stimuluscode, targetchar, filter):
    num_chars = 12
    num_repeats = 15
    num_samples = 240
    num_trials = signal.shape[0]
    # 85个字符
    num_channels = signal.shape[2]
    # 64个通道

    fb, fa = filter
    # show_filtering_result(fb, fa, signal[0,:,0])

    signal_filtered = np.zeros(signal.shape)
    for i in range(num_trials):  # 85个字符
        for j in range(num_channels):  # 64个通道
            signal_channel = signal[i,:,j]
            signal_filtered[i,:,j] = filtfilt(fb, fa, signal_channel)  # 信号滤波

    target = np.array(list(targetchar))
    data = np.zeros([num_trials, num_chars, num_repeats, num_samples, num_channels])
    for i in range(num_trials):
        repeat = np.zeros([num_chars,1], dtype=int)
        for n in range(1, signal.shape[1]):
            if flashing[i, n-1] == 0 and flashing[i, n] == 1:
                event = int(stimuluscode[i, n])
                data[i, event-1, repeat[event-1], :, :] = signal_filtered[i, n:n+num_samples, :]
                repeat[event - 1] += 1

    return data, target


def extract_feature(data, target, sampleseg, chanset, dfs):

    num_trials, num_chars, num_repeats, num_samples, num_channels = data.shape
    # data.shape: (85, 12, 15, 240, 64)
    sample_begin = sampleseg[0]  # 0
    sample_end = sampleseg[1]  # 144
    num_samples_used = int(np.ceil((sample_end - sample_begin) / dfs))
    # np.ceil((144-0)/6 = 24)对于输入24，返回最小的整数24使得 24>=24。
    num_channel_used = len(chanset)
    # 64个通道
    num_features = num_samples_used * num_channel_used

    np.seterr(divide='ignore', invalid='ignore')
    labels = np.zeros([num_trials, num_chars, num_repeats])
    feature = np.zeros([num_trials, num_chars, num_repeats, num_features])
    for trial in range(num_trials):
        target_index = matrix.find(target[trial])
        target_row = int(np.floor((target_index)/6))
        target_col = target_index - target_row * 6
        labels[trial, (target_col, target_row + 6), :] = 1

        signal_trial = data[trial]
        for char in range(num_chars):
            for repeat in range(num_repeats):
                signal_epoch = signal_trial[char, repeat, :, :]
                signal_filtered = signal_epoch[sample_begin:sample_end, chanset]
                # signal_filtered.shape:[144,64]
                signal_downsampled = np.transpose(decimate(signal_filtered.T, dfs, zero_phase=True))
                # signal_downsampled.shape：[144/6=24,64]
                # scipy.signal.decimate（要下采样的信号，降采样因子（等价地表示采样率变成原来的几分之一，通常不需要相移所以True）
                signal_normalized = np.zeros(signal_downsampled.shape)
                for c in range(num_channel_used):
                    # 如果通道仅包含直流成分，则将值设置为零。
                    if not (np.max(signal_downsampled[:, c]) == np.min(signal_downsampled[:, c])):
                        signal_normalized[:, c] = zscore(signal_downsampled[:, c])
                feature[trial, char, repeat, :] = np.reshape(signal_normalized, [-1])
                # np.reshape(signal_normalized, [-1]):把【24,64】的矩阵拉成一维向量
    return feature, labels


def load_dataset(datapath, subject):
    f = np.load(datapath+'processed/'+subject+'.npz')
    return f['featureTrain'], f['labelTrain'], f['targetTrain'], f['featureTest'], f['labelTest'], f['targetTest']


if __name__ == '__main__':
    # 6 by 6  matrix
    matrix = 'ABCDEF' + 'GHIJKL' + 'MNOPQR' + 'STUVWX' + 'YZ1234' + '56789_'

    datapath = 'E:/bcicompetition/bci2005/II/'

    import os
    if not os.path.isdir(datapath + 'processed/'):
        os.mkdir(datapath + 'processed/')

    fs = 240
    # 采样频率
    f2 = 20
    # 截止频率
    order = 6
    # 滤波器的阶数
    fb, fa = butter(order, 2 * f2 / fs, btype='low')
    # 归一化频率的具体计算方法是（2 * 截止频率) / 采样频率
    # btype='low'：低通滤波器
    # fb, fa : Butterworth滤波器系数,分子（b）和分母（a）IIR滤波器的多项式
    # show_filter(fb, fa, fs)

    dfs = 6
    sampleseg = [0, int(0.6 * fs)]
    # 序列长度【0,0.6秒*240HZ=144】
    chanset = np.arange(64)
    # chanset:[0,1,2,...,63]

    subject = 'Subject_A'
    file_train = datapath + subject + '_Train.mat'
    file_test = datapath + subject + '_Test.mat'
    file_label = datapath + 'true_labels_' + subject[-1].lower() + '.txt'

    print('Load and extract continuous EEG into epochs for train data')
    dataTrain, targetTrain = load_traindata(file_train, [fb, fa])
    print('Extract P300 features from epochs for train data')
    featureTrain, labelTrain = extract_feature(dataTrain, targetTrain, sampleseg, chanset, dfs)

    print('Load and extract continuous EEG into epochs for test data')
    dataTest, targetTest = load_testdata(file_test, file_label, [fb, fa])
    print('Extract P300 features from epochs for test data')
    featureTest, labelTest = extract_feature(dataTest, targetTest, sampleseg, chanset, dfs)

    np.savez(datapath+'processed/'+subject+'.npz',
             featureTrain=featureTrain, labelTrain=labelTrain, targetTrain=targetTrain,
             featureTest=featureTest, labelTest=labelTest, targetTest=targetTest)


