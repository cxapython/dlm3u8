# -*- coding: utf-8 -*-
# @时间 : 2020/10/30 11:16 下午
# @作者 : 陈祥安
# @文件名 : dlmp4.py
# @公众号: Python学习开发
from concurrent.futures.thread import ThreadPoolExecutor
from tqdm import tqdm
import requests
import os
from loguru import logger
import subprocess
import re
import json
import click
import glob
from Crypto.Cipher import AES

# _temp = os.path.dirname(os.path.abspath(__file__))
_temp = "/Users/chennan/studymp4"
m3u8_path = os.path.join(_temp, "m3u8")
ts_path = os.path.join(_temp, "ts_file")
mp4_path = os.path.join(_temp, "mp4_file")
if not os.path.exists(m3u8_path):
    os.makedirs(m3u8_path)
if not os.path.exists(ts_path):
    os.makedirs(ts_path)
if not os.path.exists(mp4_path):
    os.makedirs(mp4_path)
session = requests.Session()
MAX_WORKERS = 20  # 最多使用50个线程

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36",
}


def download_from_url(url, dst, file_name, aes_key=""):
    response = requests.get(url, headers=headers, stream=True, timeout=10)  # (1)
    file_size = int(response.headers['content-length'])  # (2)
    if os.path.exists(dst):
        first_byte = os.path.getsize(dst)  # (3)
    else:
        first_byte = 0
    if first_byte >= file_size:  # (4)
        logger.info(f"{file_name}:下载完毕")
        return file_size
    logger.info(f"当前下载的是:{url}")
    header = {"Range": f"bytes={first_byte}-{file_size}"}
    pbar = tqdm(
        total=file_size, initial=first_byte,
        unit='B', unit_scale=True, desc=file_name)
    req = requests.get(url, headers=header, stream=True, timeout=10)  # (5)
    with(open(dst, 'ab')) as f:
        if aes_key:
            chunk = decrypt(aes_key, req.content)
            if chunk:
                f.write(chunk)
                pbar.update(len(req.content))
        else:
            for chunk in req.iter_content(chunk_size=512):  # (6)
                if chunk:
                    f.write(chunk)
                    pbar.update(512)
    pbar.close()
    return file_size


def get_ts_file(ts_item):
    url = ts_item[0]
    name = ts_item[1]
    aes_key = ts_item[2]
    dst = os.path.join(ts_path, name)
    download_from_url(url, dst, name, aes_key)


def decrypt(key_str, content, iv_str="0" * 16):
    """
    AES解密
    :return:
    """
    aes_key = bytes(key_str, encoding='utf-8')
    aes_iv = bytes(iv_str, encoding='utf-8')
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    decrypt_bytes = cipher.decrypt(content)
    return decrypt_bytes


def read_file(prefix_url, file_path):
    with open(file_path, "r") as fs:
        index = 0
        aes_key_str = ""
        for line in fs.readlines():
            new_item = line.strip().replace("\n", "")
            if new_item.startswith("#EXT-X-KEY") and "METHOD=AES-128" in new_item:
                # 目前只有aes128的解密
                key_url = re.findall('URI="(.*?)"', new_item)[0]
                cookies = {

                }
                req = requests.get(key_url, headers=headers, cookies=cookies)
                if req.status_code in [200, 201]:
                    aes_key_str = req.text
                    print(f"获取密钥:{aes_key_str}")
            if new_item.endswith(".ts"):
                if "/" in new_item:
                    new_item = new_item.split("/")[-1]
                index += 1
                yield f"{prefix_url}/{new_item}", f"{index}.ts", aes_key_str


def get_m3u8(download_url, file_path):
    req = session.get(download_url)
    buff = req.content
    with open(file_path, "wb") as fs:
        fs.write(buff)


def merge_ts_file(file_name):
    file_list = sorted(int(item.replace(".ts", ""))
                       for item in os.listdir(ts_path) if ".ts" in item)

    merge_text_path = os.path.join(ts_path, f"{file_name}_merge_file.txt")
    with open(merge_text_path, "w+") as f:
        for index, file in enumerate(file_list):
            content = f"file '{file}.ts'\n"
            if index == len(file_list) - 1:
                content = f"file '{file}.ts'"
            f.write(content)
    return merge_text_path


def gen_mp4_file(file_name, text_path):
    mp4_file_name = f"{file_name}.mp4"
    mp4_full_path = os.path.join(mp4_path, mp4_file_name)
    os.chdir(ts_path)
    retval = os.getcwd()
    print(f"当前目录:{retval}")
    command = f"ffmpeg -f concat -safe 0 -i '{text_path}' -c copy '{mp4_full_path}'"
    print(command)
    try:
        completed = subprocess.run(command, check=True, shell=True,
                                   stdout=subprocess.PIPE)
        result = completed.stdout.decode("utf-8")
        print(f"code:{completed.returncode}")
        if completed.returncode != 0:
            raise
        # for ts_file in glob.glob(os.path.join(ts_path, '*.*')):
        #     os.remove(ts_file)
        logger.info(f"{mp4_file_name} 合并完成！")
    except subprocess.CalledProcessError:
        logger.error(f"{mp4_file_name},转换失败")
    except Exception:
        logger.error("异常退出")


def get_seed(video_id):
    referer = f"https://jj.009xf.com/YaZhoux/{video_id}.html"
    url_list = [f"https://jj.009xf.com/play/{video_id}/{index}/1.html" for index in range(1, 4)]
    for url in url_list:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36",
            "Referer": referer
        }
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            source = resp.text
            url_arr = re.findall("var player_data=(.*?)</script>", source)
            name_arr = re.findall("'vod_name'.*?\"(.*?)\",", source)
            result = url_arr[0] if url_arr else ""
            file_name = name_arr[0].strip().replace("\n", "").replace(" ", "") if name_arr else ""
            if result and file_name:
                json_data = json.loads(result)
                m3u8_url = json_data.get("url")
                if m3u8_url:
                    return m3u8_url, file_name


@click.command()
@click.option('-i', '--video_id', type=str, help='fetch id')
@click.option('-u', '--input_url', type=str, help='fetch url')
@click.option('-n', '--name', type=str, help='file name')
def main(video_id, input_url, name):
    if input_url:
        url = input_url
        m3u8_file_name = file_name = os.path.basename(url)
    elif video_id:
        url, file_name = get_seed(video_id)
        m3u8_file_name = file_name
    if name:
        m3u8_file_name = name

    prefix_url = os.path.dirname(url)
    m3u8_file_path = os.path.join(m3u8_path, f"{m3u8_file_name}.m3u8")
    logger.info(f"file_name:{m3u8_file_name},url:{url}")
    get_m3u8(url, m3u8_file_path)
    ts_item_gen = read_file(prefix_url, m3u8_file_path)
    with ThreadPoolExecutor(MAX_WORKERS) as excutor:
        excutor.map(get_ts_file, ts_item_gen)
    logger.info("全部下载完成")
    logger.info("生成ts文件列表")
    merge_text_path = merge_ts_file(m3u8_file_name)
    logger.info("生成mp4")
    gen_mp4_file(file_name, merge_text_path)


if __name__ == '__main__':
    main()
