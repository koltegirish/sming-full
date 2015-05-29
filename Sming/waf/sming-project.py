#! /usr/bin/env python
# encoding: utf-8
import os

from waflib.TaskGen import feature, after_method, after, extension
from pprint import pprint
from waflib.Task import Task
from waflib.Tools.ccroot import link_task, stlink_task
from waflib import Utils

####appgen

import string
import sys
#import os
import re
import binascii
import struct

TEXT_ADDRESS = 0x40100000
# app_entry = 0
# data_address = 0x3ffb0000
# data_end  = 0x40000000
# text_end  = 0x40120000

CHECKSUM_INIT = 0xEF

chk_sum = CHECKSUM_INIT
blocks = 0


top = '.'
out = 'build'

####
class cxxprogram_custom(link_task):
    "Link object files into a c++ program"
    run_str = '${LINK_CXX} ${LINKFLAGS} ${CXXLNK_SRC_F}${SRC} ${CXXLNK_TGT_F}${TGT[0].abspath()} ${RPATH_ST:RPATH} ${FRAMEWORKPATH_ST:FRAMEWORKPATH} ${FRAMEWORK_ST:FRAMEWORK} ${ARCH_ST:ARCH} ${STLIB_MARKER} ${STLIBPATH_ST:STLIBPATH} ${STLIB_ST:STLIB} ${SHLIB_MARKER} ${LIBPATH_ST:LIBPATH} ${LIB_ST:LIB}'
    vars    = ['LINKDEPS']
    ext_out = ['.bin']
    inst_to = '${BINDIR}'
    chmod   = Utils.O755


def write_file(file_name,data):
    if file_name is None:
        print 'file_name cannot be none\n'
        # sys.exit(0)

    fp = open(file_name,'ab')

    if fp:
        fp.seek(0,os.SEEK_END)
        fp.write(data)
        fp.close()
    else:
        print '%s write fail\n'%(file_name)

def combine_bin(file_name,dest_file_name,start_offset_addr,need_chk):
    global chk_sum
    global blocks
    if dest_file_name is None:
        print 'dest_file_name cannot be none\n'
        # sys.exit(0)

    if file_name:
        fp = open(file_name,'rb')
        if fp:
            ########## write text ##########
            fp.seek(0,os.SEEK_END)
            data_len = fp.tell()
            if data_len:
                if need_chk:
                    tmp_len = (data_len + 3) & (~3)
                else:
                    tmp_len = (data_len + 15) & (~15)
                data_bin = struct.pack('<II',start_offset_addr,tmp_len)
                write_file(dest_file_name,data_bin)
                fp.seek(0,os.SEEK_SET)
                data_bin = fp.read(data_len)
                write_file(dest_file_name,data_bin)
                if need_chk:
                    for loop in range(len(data_bin)):
                        chk_sum ^= ord(data_bin[loop])
                # print '%s size is %d(0x%x),align 4 bytes,\nultimate size is %d(0x%x)'%(file_name,data_len,data_len,tmp_len,tmp_len)
                tmp_len = tmp_len - data_len
                if tmp_len:
                    data_str = ['00']*(tmp_len)
                    data_bin = binascii.a2b_hex(''.join(data_str))
                    write_file(dest_file_name,data_bin)
                    if need_chk:
                        for loop in range(len(data_bin)):
                            chk_sum ^= ord(data_bin[loop])
                blocks = blocks + 1
                fp.close()
        else:
            print '!!!Open %s fail!!!'%(file_name)

@extension('.out')
def app_gen(self):
    pprint(self)
    print('app_gen')
    pprint(self.inputs[0].abspath())
    global chk_sum
    global blocks
    # if len(sys.argv) != 6:
    #     print 'Usage: gen_appbin.py eagle.app.out boot_mode flash_mode flash_clk_div flash_size'
    #     # sys.exit(0)

    elf_file = self.inputs[0].abspath()    
    boot_mode = 0
    flash_mode = 0
    flash_clk_div = 0
    flash_size = 0

    flash_data_line  = 16
    data_line_bits = 0xf

    irom0text_bin_name = 'build/eagle.app.v6.irom0text.bin'
    text_bin_name = 'build/eagle.app.v6.text.bin'
    data_bin_name = 'build/eagle.app.v6.data.bin'
    rodata_bin_name = 'build/eagle.app.v6.rodata.bin'
    flash_bin_name ='build/eagle.app.flash.bin'

    BIN_MAGIC_FLASH  = 0xE9
    BIN_MAGIC_IROM   = 0xEA
    data_str = ''
    sum_size = 0

    cmd = 'C:\\Espressif\\xtensa-lx106-elf\\bin\\xtensa-lx106-elf-nm -g ' + elf_file + ' > build/eagle.app.sym'

    os.system(cmd)

    fp = file('build/eagle.app.sym')
    if fp is None:
        print "open sym file error\n"
        # sys.exit(0)

    lines = fp.readlines()
    fp.close()

    entry_addr = None
    p = re.compile('(\w*)(\sT\s)(call_user_start)$')
    for line in lines:
        m = p.search(line)
        if m != None:
            entry_addr = m.group(1)
            # print entry_addr

    if entry_addr is None:
        print 'no entry point!!'
        # sys.exit(0)

    data_start_addr = '0'
    p = re.compile('(\w*)(\sA\s)(_data_start)$')
    for line in lines:
        m = p.search(line)
        if m != None:
            data_start_addr = m.group(1)
            # print data_start_addr

    rodata_start_addr = '0'
    p = re.compile('(\w*)(\sA\s)(_rodata_start)$')
    for line in lines:
        m = p.search(line)
        if m != None:
            rodata_start_addr = m.group(1)
            # print rodata_start_addr

    # write flash bin header
    #============================
    #  SPI FLASH PARAMS
    #-------------------
    #flash_mode=
    #     0: QIO
    #     1: QOUT
    #     2: DIO
    #     3: DOUT
    #-------------------
    #flash_clk_div=
    #     0 :  80m / 2
    #     1 :  80m / 3
    #     2 :  80m / 4
    #    0xf:  80m / 1
    #-------------------
    #flash_size=
    #     0 : 512 KB
    #     1 : 256 KB
    #     2 : 1024 KB
    #     3 : 2048 KB
    #     4 : 4096 KB
    #-------------------
    #   END OF SPI FLASH PARAMS
    #============================
    byte2=int(flash_mode)&0xff
    byte3=(((int(flash_size)<<4)| int(flash_clk_div))&0xff)
    
    if boot_mode == '2':
        # write irom bin head
        data_bin = struct.pack('<BBBBI',BIN_MAGIC_IROM,4,byte2,byte3,long(entry_addr,16))
        sum_size = len(data_bin)
        write_file(flash_bin_name,data_bin)
        
        # irom0.text.bin
        combine_bin(irom0text_bin_name,flash_bin_name,0x0,0)

    data_bin = struct.pack('<BBBBI',BIN_MAGIC_FLASH,3,byte2,byte3,long(entry_addr,16))
    sum_size = len(data_bin)
    write_file(flash_bin_name,data_bin)

    # text.bin
    combine_bin(text_bin_name,flash_bin_name,TEXT_ADDRESS,1)

    # data.bin
    if data_start_addr:
        combine_bin(data_bin_name,flash_bin_name,long(data_start_addr,16),1)

    # rodata.bin
    combine_bin(rodata_bin_name,flash_bin_name,long(rodata_start_addr,16),1)

    # write checksum header
    sum_size = os.path.getsize(flash_bin_name) + 1
    sum_size = flash_data_line - (data_line_bits&sum_size)
    if sum_size:
        data_str = ['00']*(sum_size)
        data_bin = binascii.a2b_hex(''.join(data_str))
        write_file(flash_bin_name,data_bin)
    write_file(flash_bin_name,chr(chk_sum & 0xFF))
        
    if boot_mode == '1':
        sum_size = os.path.getsize(flash_bin_name)
        data_str = ['FF']*(0x10000-sum_size)
        data_bin = binascii.a2b_hex(''.join(data_str))
        write_file(flash_bin_name,data_bin)

        fp = open(irom0text_bin_name,'rb')
        if fp:
            data_bin = fp.read()
            write_file(flash_bin_name,data_bin)
            fp.close()
        else :
            print '!!!Open %s fail!!!'%(flash_bin_name)
            # sys.exit(0)

    os.remove("build/eagle.app.sym")
    # cmd = 'del eagle.app.sym'
    # os.system(cmd)

def post(ctx):
    pass


from waflib.Configure import conf

def options(ctx):
    ctx.load('gcc gxx python')

    ctx.add_option("--shared", action="store_true", help="build shared library")
    ctx.add_option("--static", action="store_true", help="build static library")
    ctx.add_option("--fgghstatic", action="store_true", help="build static library11")

def configure(ctx):
    # Temp hardcoeded until have conditionals
    ctx.env.FW_APP = 0
    ctx.env.FW_MODE = 0
    ctx.env.FW_FREQDIV = 0
    ctx.env.FW_SIZE = 0

    ctx.env.CC = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/bin/xtensa-lx106-elf-gcc.exe'))
    ctx.env.CXX = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/bin/xtensa-lx106-elf-g++.exe'))

    ctx.env.LINK_CC = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/bin/xtensa-lx106-elf-gcc.exe'))
    ctx.env.LINK_CXX = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/bin/xtensa-lx106-elf-g++.exe'))

    ctx.env.AR = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/bin/xtensa-lx106-elf-ar.exe'))
    ctx.env.NM = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/bin/xtensa-lx106-elf-nm.exe'))

    ctx.env.ARFLAGS = ['cru']

    ctx.load('gcc gxx python')
    ctx.check_python_version((2, 7, 5))

    ctx.env.CFLAGS = ['-Os', '-g', '-Wpointer-arith', '-Wundef', '-Werror', '-Wl,-EL', '-nostdlib', '-mlongcalls', '-mtext-section-literals', '-finline-functions', '-fdata-sections', '-ffunction-sections', '-D__ets__', '-DICACHE_FLASH', '-DARDUINO=106']
    ctx.env.CXXFLAGS = ctx.env.CFLAGS + ['-fno-rtti', '-fno-exceptions', '-std=c++11']

    ctx.env.OBJCOPY = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/bin/xtensa-lx106-elf-objcopy.exe'))
    ctx.env.GEN_APPBIN = os.path.normpath(os.path.join(os.environ.ESP_HOME, 'utils/gen_appbin.py'))

    ctx.env.INCLUDES = [
        os.path.normpath(os.environ.SMING_HOME),
        os.path.normpath(os.environ.ESP_HOME),
        'include',
        os.path.normpath(os.path.join(os.environ.SMING_HOME, 'incude')),
        os.path.normpath(os.path.join(os.environ.SMING_HOME, 'Wiring')),
        os.path.normpath(os.path.join(os.environ.SMING_HOME, 'Libraries')),
        os.path.normpath(os.path.join(os.environ.SMING_HOME, 'SmingCore')),
        os.path.normpath(os.path.join(os.environ.SMING_HOME, 'system/include')),
        os.path.normpath(os.path.join(os.environ.ESP_HOME, 'sdk/include'))
    ]

    ctx.env.STLIBPATH = [
        os.path.normpath(os.path.join(os.environ.SMING_HOME, 'compiler/lib')),
        os.path.normpath(os.path.join(os.environ.ESP_HOME, 'sdk/lib')),
        os.path.normpath(os.path.join(os.environ.ESP_HOME, 'xtensa-lx106-elf/xtensa-lx106-elf/sysroot/usr/lib'))
    ]

    ctx.env.STLIB = [
        'main',
        'sming',
        'phy',
        'pp',
        'lwip',
        'net80211',
        'wpa',
        'hal',
        'microc',
        'microgcc',
    ]

    ctx.env.COMPILE = 'gcc'
    ctx.env.LDSCRIPT = os.path.normpath(os.path.join(os.environ.SMING_HOME, 'compiler/ld/eagle.app.v6.cpp.ld'))

    ctx.env.LINKFLAGS = [
        '-nostdlib',
        '-u call_user_start',
        '-Wl,-static',
        '-Wl,--gc-sections',
        '-T'+ctx.env.LDSCRIPT,
        '-Wl,--start-group'
    ]

    ctx.env.LDFLAGS = ['-Wl,--end-group']

    init_template = 'void init() {}'
    ctx.check_cxx(lib='microc', fragment=init_template)
    ctx.check_cxx(lib='hal', fragment=init_template)
    ctx.check_cxx(lib='phy', fragment=init_template)
    ctx.check_cxx(lib='pp', fragment=init_template)
    ctx.check_cxx(lib='net80211', fragment=init_template)
    ctx.check_cxx(lib='openlwip', fragment=init_template)
    ctx.check_cxx(lib='wpa', fragment=init_template)

    ctx.check_cxx(lib='main', fragment=init_template)
    ctx.check_cxx(lib='sming', fragment=init_template)



def build(ctx):

    # ctx.program(
    #     source=ctx.path.ant_glob('**/*.cpp')+[ctx.root.find_resource(os.path.normpath(os.path.join(os.environ.SMING_HOME, 'appinit/user_main.cpp')))],
    #     target='app.out',
    # )

    ctx(
        source=ctx.path.ant_glob('**/*.cpp')+[ctx.root.find_resource(os.path.normpath(os.path.join(os.environ.SMING_HOME, 'appinit/user_main.cpp')))],
        target='app.out',
        features='cxx cxxprogram_custom',
    )

    ctx(rule='${OBJCOPY} --only-section .text -O binary ${SRC} ${TGT}', source='app.out', target='eagle.app.v6.text.bin', name='eagle.app.v6.text.bin')
    ctx(rule='${OBJCOPY} --only-section .data -O binary ${SRC} ${TGT}', source='app.out', target='eagle.app.v6.data.bin')
    ctx(rule='${OBJCOPY} --only-section .rodata -O binary ${SRC} ${TGT}', source='app.out', target='eagle.app.v6.rodata.bin')
    ctx(rule='${OBJCOPY} --only-section .irom0.text -O binary ${SRC} ${TGT}', source='app.out', target='eagle.app.v6.irom0text.bin')
    

    ctx.add_post_fun(post)
    os.environ['COMPILE'] = 'gcc'

    if ctx.env.FW_APP == 0:
        ctx(rule=app_gen, tt='test', source='app.out')
        # ctx(rule='${GEN_APPBIN} ${SRC} 0 0 0 0', source='app.out', target='eagle.app.flash.bin')
        # ctx(rule='echo ${COMPILE}', source='app.out')

    
