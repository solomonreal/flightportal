import displayio

# Define constants
PLANE_COLOUR = 0xFFFFFF

# Little plane to scroll across when we find a flight overhead
planeBmp = displayio.Bitmap(12, 12, 2)
planePalette = displayio.Palette(2)
planePalette[1] = PLANE_COLOUR
planePalette[0] = 0x000000
planeBmp[6,0]=planeBmp[6,1]=planeBmp[5,1]=planeBmp[4,2]=planeBmp[5,2]=planeBmp[6,2]=1
planeBmp[9,3]=planeBmp[5,3]=planeBmp[4,3]=planeBmp[3,3]=1
planeBmp[1,4]=planeBmp[2,4]=planeBmp[3,4]=planeBmp[4,4]=planeBmp[5,4]=planeBmp[6,4]=planeBmp[7,4]=planeBmp[8,4]=planeBmp[9,4]=1
planeBmp[1,5]=planeBmp[2,5]=planeBmp[3,5]=planeBmp[4,5]=planeBmp[5,5]=planeBmp[6,5]=planeBmp[7,5]=planeBmp[8,5]=planeBmp[9,5]=1
planeBmp[9,6]=planeBmp[5,6]=planeBmp[4,6]=planeBmp[3,6]=1
planeBmp[6,9]=planeBmp[6,8]=planeBmp[5,8]=planeBmp[4,7]=planeBmp[5,7]=planeBmp[6,7]=1
planeTg= displayio.TileGrid(planeBmp, pixel_shader=planePalette)
planeG=displayio.Group(x=matrixportal.display.width+12,y=10)
planeG.append(planeTg)

# Create "taking off" animation
taking_off_bmp = displayio.Bitmap(12, 12, 2)
taking_off_palette = displayio.Palette(2)
taking_off_palette[1] = PLANE_COLOUR
taking_off_palette[0] = 0x000000
taking_off_bmp[6, 11] = taking_off_bmp[6, 10] = taking_off_bmp[5, 10] = taking_off_bmp[4, 9] = taking_off_bmp[5, 9] = taking_off_bmp[6, 9] = 1
taking_off_bmp[9, 8] = taking_off_bmp[5, 8] = taking_off_bmp[4, 8] = taking_off_bmp[3, 8] = 1
taking_off_bmp[1, 7] = taking_off_bmp[2, 7] = taking_off_bmp[3, 7] = taking_off_bmp[4, 7] = taking_off_bmp[5, 7] = taking_off_bmp[6, 7] = taking_off_bmp[7, 7] = taking_off_bmp[8, 7] = taking_off_bmp[9, 7] = 1
taking_off_bmp[1, 6] = taking_off_bmp[2, 6] = taking_off_bmp[3, 6] = taking_off_bmp[4, 6] = taking_off_bmp[5, 6] = taking_off_bmp[6, 6] = taking_off_bmp[7, 6] = taking_off_bmp[8, 6] = taking_off_bmp[9, 6] = 1
taking_off_bmp[9, 5] = taking_off_bmp[5, 5] = taking_off_bmp[4, 5] = taking_off_bmp[3, 5] = 1
taking_off_bmp[6, 2] = taking_off_bmp[6, 1] = taking_off_bmp[5, 1] = taking_off_bmp[4, 0] = taking_off_bmp[5, 0] = taking_off_bmp[6, 0] = 1
taking_off_tg = displayio.TileGrid(taking_off_bmp, pixel_shader=taking_off_palette)
taking_off_g = displayio.Group(x=matrixportal.display.width + 12, y=10)
taking_off_g.append(taking_off_tg)

# Create "landing" animation
landing_bmp = displayio.Bitmap(12, 12, 2)
landing_palette = displayio.Palette(2)
landing_palette[1] = PLANE_COLOUR
landing_palette[0] = 0x000000
landing_bmp[6, 0] = landing_bmp[6, 1] = landing_bmp[5, 1] = landing_bmp[4, 2] = landing_bmp[5, 2] = landing_bmp[6, 2] = 1
landing_bmp[9, 3] = landing_bmp[5, 3] = landing_bmp[4, 3] = landing_bmp[3, 3] = 1
landing_bmp[1, 4] = landing_bmp[2, 4] = landing_bmp[3, 4] = landing_bmp[4, 4] = landing_bmp[5, 4] = landing_bmp[6, 4] = landing_bmp[7, 4] = landing_bmp[8, 4] = landing_bmp[9, 4] = 1
landing_bmp[1, 5] = landing_bmp[2, 5] = landing_bmp[3, 5] = landing_bmp[4, 5] = landing_bmp[5, 5] = landing_bmp[6, 5] = landing_bmp[7, 5] = landing_bmp[8, 5] = landing_bmp[9, 5] = 1
landing_bmp[9, 6] = landing_bmp[5, 6] = landing_bmp[4, 6] = landing_bmp[3, 6] = 1
landing_bmp[6, 9] = landing_bmp[6, 8] = landing_bmp[5, 8] = landing_bmp[4, 7] = landing_bmp[5, 7] = landing_bmp[6, 7] = 1
landing_tg = displayio.TileGrid(landing_bmp, pixel_shader=landing_palette)
landing_g = displayio.Group(x=matrixportal.display.width + 12, y=matrixportal.display.height - 12)
landing_g.append(landing_tg)

# You can then use these groups (taking_off_g and landing_g) as needed in your main script.
# For example, you can add them to a display group for rendering and animation control.
