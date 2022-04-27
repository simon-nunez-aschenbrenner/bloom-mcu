# BLOOM Hub Display Image Conversion
#
# Convert an image for a 128x64px display using framebuf.MONO_VLSB
# Input must be a 128x64px grayscale image, with only fully black or white pixels, no gray values
# Output is a binary file
# Refer to the MicroPython SSD1306 OLED driver and https://docs.micropython.org/en/latest/library/framebuf.html#framebuf.framebuf.MONO_VLSB
#
# Author: Simon Aschenbrenner

import matplotlib.image as mpi

input = 'logo.png'
output = 'logo'

logo = mpi.imread(input).astype(int)
buffer = bytearray()

for i in range(7, -1, -1):
    for j in range(127, -1, -1):
        column = logo[i*8:i*8+8, j]
        byte = 0
        for pos, bit in enumerate(column):
            byte += (bit << 7-pos)
        buffer.append(byte)

with open(output, 'wb') as binary_file:
    binary_file.write(buffer)

# Example for using the binary file as the buffer of an SSD1306 instance named 'display'
# For an unknown reason the SSD1306 driver or framebuf methods cannot modify the buffer afterwards?
# Current workaround: Reinitialized the display to resume normal operation
"""
with open(output, 'rb') as binary_file:
    buffer = bytearray(1024)
    binary_file.readinto(buffer)
    display.buffer = buffer
display.show()
"""