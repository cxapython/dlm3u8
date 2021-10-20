# dlm3u8
下载常规的m3u8文件，支持断点续下

# 依赖
安装ffmpeg到系统
```
# mac为例
brew install ffmpeg
```


# 运行
```

python3.6 dlm3u8.py -n "xxx_class8" -p "https://video.xxx.com" -t 1 -l 1
```
-n:表示文件名
-p:是m3u8里面ts文件补全用的前缀
-t:是下载线程数默认2
-l:表示加载本地m3u8文件