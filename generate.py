import sys
import glob
import os
import argparse

import numpy
import librosa
import chainer

from models import VAE
from utils import mu_law
from utils import Preprocess
import opt

parser = argparse.ArgumentParser()
parser.add_argument('--input', '-i', help='input file')
parser.add_argument('--output', '-o', help='output file')
parser.add_argument('--model', '-m', help='snapshot of trained model')
parser.add_argument('--speaker', '-s', default=None,
                    help='name of speaker. if this is None,'
                         'input speaker is used.')
parser.add_argument('--gpu', '-g', type=int, default=-1,
                    help='GPU ID (negative value indicates CPU)')
args = parser.parse_args()

# set data
if opt.dataset == 'VCTK':
    speakers = glob.glob(os.path.join(opt.root, 'wav48/*'))
elif opt.dataset == 'ARCTIC':
    speakers = glob.glob(os.path.join(opt.root, '*'))
path = args.input

n_speaker = len(speakers)
speaker_dic = {
    os.path.basename(speaker): i for i, speaker in enumerate(speakers)}

# make model
model = VAE(opt.d, opt.k, opt.n_loop, opt.n_layer, opt.n_filter, opt.mu,
            opt.residual_channels, opt.dilated_channels, opt.skip_channels,
            opt.embed_channels, opt.beta, n_speaker)
chainer.serializers.load_npz(args.model, model, 'updater/model:main/')

if args.gpu >= 0:
    use_gpu = True
    chainer.cuda.get_device_from_id(args.gpu).use()
    model.to_gpu()
else:
    use_gpu = False

# preprocess
n = 1
inputs = Preprocess(
    opt.data_format, opt.sr, opt.mu, opt.top_db,
    None, opt.dataset, speaker_dic, False)(path)

raw, one_hot, speaker, quantized = inputs
raw = numpy.expand_dims(raw, 0)
one_hot = numpy.expand_dims(one_hot, 0)

print('from speaker', speaker)
if args.speaker is None:
    speaker = numpy.expand_dims(speaker, 0)
elif args.speaker in speaker_dic:
    speaker = numpy.asarray([speaker_dic[args.speaker]], dtype=numpy.int32)
else:
    speaker = numpy.asarray([args.speaker], dtype=numpy.int32)
print('to speaker', speaker[0])

quantized = numpy.expand_dims(quantized, 0)

# forward
if use_gpu:
    raw = chainer.cuda.to_gpu(raw, device=args.gpu)
    speaker = chainer.cuda.to_gpu(speaker, device=args.gpu)
output = model.generate(raw, speaker)
if use_gpu:
    output = chainer.cuda.to_cpu(output)
wave = mu_law(opt.mu).itransform(output)
librosa.output.write_wav(args.output, wave, opt.sr)
