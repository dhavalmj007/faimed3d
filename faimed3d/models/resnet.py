# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/06b_models.resnet.ipynb (unless otherwise specified).

__all__ = ['conv3x3', 'conv1x1', 'BasicBlock3d', 'Bottleneck3d', 'IdentityLayer', 'ResNet3D', 'resnet18_3d',
           'resnet34_3d', 'resnet50_3d', 'resnet101_3d', 'resnet152_3d', 'build_backbone']

# Cell
# export
from fastai.basics import *
from fastai.layers import *
from warnings import warn
from torch.hub import load_state_dict_from_url

# Cell
from torchvision.models.resnet import Bottleneck, BasicBlock

def conv3x3(in_planes, out_planes, stride=1, groups=1, dilation=1):
    """3x3 convolution with padding"""
    return nn.Conv3d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=dilation, groups=groups, bias=False, dilation=dilation)

def conv1x1(in_planes, out_planes, stride=1):
    """1x1 convolution"""
    return nn.Conv3d(in_planes, out_planes, kernel_size=1, stride=stride, bias=False)

from torch import nn # prevent error in nbdev with re-importing nn (was already imported with fastai)
class BasicBlock3d(nn.Module):
    expansion = 1
    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None, act_layer=None):
        super(BasicBlock3d, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm3d
        if act_layer is None:
            act_layer = partial(nn.ReLU, inplace=True)
        if groups != 1 or base_width != 64:
            raise ValueError('BasicBlock only supports groups=1 and base_width=64')
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = act_layer()
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out

class Bottleneck3d(nn.Module):
    expansion = 4
    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None, act_layer=None):
        super(Bottleneck3d, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm3d
        if act_layer is None:
            act_layer = partial(nn.ReLU, inplace=True)
        width = int(planes * (base_width / 64.)) * groups
        # Both self.conv2 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv1x1(inplanes, width)
        self.bn1 = norm_layer(width)
        self.conv2 = conv3x3(width, width, stride, groups, dilation)
        self.bn2 = norm_layer(width)
        self.conv3 = conv1x1(width, planes * self.expansion)
        self.bn3 = norm_layer(planes * self.expansion)
        self.relu = act_layer()
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)


        return out

# Cell
class IdentityLayer(nn.Module):
    "Returns input as is"
    def __init__(self, *args, **kwargs):
        super(IdentityLayer, self).__init__()
    def forward(self, x):
        return x

# Cell
class ResNet3D(nn.Module):

    def __init__(self, block, layers, n_channels=3, num_classes=101, zero_init_residual=False,
                 groups=1, width_per_group=64, replace_stride_with_dilation=None,
                 norm_layer=None, act_layer=None, final_softmax=False, ps = 0.5):
        super(ResNet3D, self).__init__()
        if norm_layer is None: norm_layer = nn.BatchNorm3d
        if act_layer is None: act_layer = partial(nn.ReLU, inplace=True)
        self._norm_layer = norm_layer
        self.inplanes = 128 if isinstance(block(1,1), Bottleneck3d) else 32

        self.dilation = 1
        if replace_stride_with_dilation is None:
            # each element in the tuple indicates if we should replace
            # the 2x2 stride with a dilated convolution instead
            replace_stride_with_dilation = [False, False, False]
        if len(replace_stride_with_dilation) != 3:
            raise ValueError("replace_stride_with_dilation should be None "
                             "or a 3-element tuple, got {}".format(replace_stride_with_dilation))
        self.groups = groups
        self.base_width = width_per_group

        self.stem = nn.Sequential(nn.Conv3d(n_channels, self.inplanes, kernel_size=(2, 5, 5), stride=(1, 3, 3), padding=1, bias=False),
                                  norm_layer(self.inplanes),
                                  act_layer(inplace=True))

        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2,
                                       dilate=replace_stride_with_dilation[0])
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2,
                                       dilate=replace_stride_with_dilation[1])
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2,
                                       dilate=replace_stride_with_dilation[2])
        self.avgpool = nn.AdaptiveAvgPool3d((1, 1, 1))
        self.fc = nn.Sequential(
            nn.BatchNorm1d(512 * block.expansion, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True),
            nn.Dropout(p=ps/2, inplace=False),
            nn.Linear(512 * block.expansion, 256),
            act_layer(inplace=True),
            nn.BatchNorm1d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True),
            nn.Dropout(p=ps, inplace=False),
            nn.Linear(256, num_classes,bias = False))

        if final_softmax:
            self.fc = nn.Sequential(self.fc,
                                    nn.Softmax(1))

        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, (nn.BatchNorm3d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

        # Zero-initialize the last BN in each residual branch,
        # so that the residual branch starts with zeros, and each residual block behaves like an identity.
        # This improves the model by 0.2~0.3% according to https://arxiv.org/abs/1706.02677
        if zero_init_residual:
            for m in self.modules():
                if isinstance(m, Bottleneck3d):
                    nn.init.constant_(m.bn3.weight, 0)
                elif isinstance(m, BasicBlock3d):
                    nn.init.constant_(m.bn2.weight, 0)

    def _make_layer(self, block, planes, blocks, stride=1, dilate=False):
        norm_layer = self._norm_layer
        downsample = None
        previous_dilation = self.dilation
        if dilate:
            self.dilation *= stride
            stride = 1
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                conv1x1(self.inplanes, planes * block.expansion, stride),
                norm_layer(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, self.groups,
                            self.base_width, previous_dilation, norm_layer))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes, groups=self.groups,
                                base_width=self.base_width, dilation=self.dilation,
                                norm_layer=norm_layer))

        return nn.Sequential(*layers)

    def _encoder(self, x1):
        x2 = self.layer1(x1)
        x3 = self.layer2(x2)
        x4 = self.layer3(x3)
        x5 = self.layer4(x4)
        return x2, x3, x4, x5

    def _head(self, x5):
        x = self.avgpool(x5)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x

    def _forward_impl(self, x):
        # See note [TorchScript super()]
        x = self.stem(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x

    def forward(self, x):
        return self._forward_impl(x)

# Cell
_model_urls = {
           'resnet18_3d': 'https://rad-ai.charite.de/pretrained_models/resnet18_3d_ucf100.pth',
           'resnet34_3d': 'https://rad-ai.charite.de/pretrained_models/resnet34_3d_ucf100.pth',
           'resnet50_3d': 'https://rad-ai.charite.de/pretrained_models/resnet50_3d_ucf100.pth',
           'resnet101_3d': 'https://rad-ai.charite.de/pretrained_models/resnet101_3d_ucf100.pth'
          }

# Cell

def _resnet_3d(arch, block, layers, pretrained=False, progress=False, **kwargs):
    "similar to the _resnet function of pytorch. Has same Args as resnet for compatibility, but does not us them all"
    model = ResNet3D(block, layers, **kwargs)
    if pretrained:
        state_dict = load_state_dict_from_url(_model_urls[arch],
                                              progress=True)
        model.load_state_dict(state_dict['model'])
    return model

# Cell
def resnet18_3d(pretrained=False, progress=False, **kwargs):
    r"""ResNet-34 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_
    adapted to 3d
    """
    return _resnet_3d('resnet18_3d', BasicBlock3d, [2, 2, 2, 2], pretrained=pretrained, progress=progress,**kwargs)


def resnet34_3d(pretrained=False, progress=False, **kwargs):
    r"""ResNet-34 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_
    adapted to 3d
    """
    return _resnet_3d('resnet34_3d', BasicBlock3d, [3, 4, 6, 3], pretrained=pretrained, progress=progress,**kwargs)


def resnet50_3d(pretrained=False, progress=False,**kwargs):
    r"""ResNet-50 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_
    adapted to 3d
    """
    return _resnet_3d('resnet50_3d', Bottleneck3d, [3, 4, 6, 3], pretrained=pretrained, progress=progress,**kwargs)


def resnet101_3d(pretrained=False, progress=False, **kwargs):
    r"""ResNet-101 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`
    adapted to 3d
    """
    return _resnet_3d('resnet101_3d', Bottleneck3d, [3, 4, 23, 3], pretrained=pretrained, progress=progress,**kwargs)


def resnet152_3d(pretrained=False, progress=False, **kwargs):
    r"""ResNet-152 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`
    adapted to 3d
    """
    # currently no pretrained version. Might follow in the future
    if pretrained: warn('Currently there is no pretrained version available for `resnet152_3d`. Will load randomly intilialized weights.')
    return _resnet_3d(None, Bottleneck3d, [3, 8, 36, 3], pretrained=False, progress=False,**kwargs)

# Cell
def build_backbone(backbone, output_stride, norm_layer, n_channels, **kwargs):
    model = backbone(n_channels=n_channels, norm_layer=norm_layer, **kwargs) #output_stride, BatchNorm)
    def forward(x):
        x1=model.stem(x)
        x2=model.layer1(x1)
        x3=model.layer2(x2)
        x4=model.layer3(x3)
        x5=model.layer4(x4)
        return x1, x2, x3, x4, x5
    model.forward = forward
    return model