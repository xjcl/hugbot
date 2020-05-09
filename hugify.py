import PIL.ImageChops
import PIL.ImageFont
import PIL.ImageDraw
import PIL.ImageOps
import PIL.Image
import imageio
import random
import numpy
import glob
import sys
import os


# how to position 1-3 images (x, y, scaling)
alignments = [
    [(126,   0, 260)],
    [(-14, -40, 200), (340-14, -40, 200)],
    [(-14, -40, 200), (170-14,  60, 200), (340-14, -40, 200)],
]

# work independently of call site
script_dir = os.path.dirname(os.path.realpath(__file__))

# cache these in RAM
base_grin  = PIL.Image.open(os.path.join(script_dir, 'twitter-grin-emoji-rgba.png')).convert('RGBA')
base_smile = PIL.Image.open(os.path.join(script_dir, 'twitter-hug-emoji_base_full.png')).convert('RGBA')
hand_l = PIL.Image.open(os.path.join(script_dir, 'twitter-waving-hand-sign-emoji-pure-outside.png')).convert('RGBA')

base_grin  = base_grin.crop((0, 0, base_grin.width, base_grin.height + 180))  # 512 x 512+y_offset
base_smile = base_smile.crop((0, 0, base_smile.width, base_smile.height + 100))  # 512 x 512+y_offset
hand_l = hand_l.resize((260, 260))
hand_r = hand_l.transpose(PIL.Image.FLIP_LEFT_RIGHT)


def resize_and_center(image, new_dim):
    '''Profile pictures are always square, but custom attachments might not be'''
    ratio = min(new_dim[0]/image.width, new_dim[1]/image.height)
    image = image.resize((int(ratio * image.width), int(ratio * image.height)))
    delta_w = new_dim[0] - image.width
    delta_h = new_dim[1] - image.height
    padding = (delta_w//2, delta_h//2, delta_w-(delta_w//2), delta_h-(delta_h//2))
    return PIL.ImageOps.expand(image, padding)


def hugged(people, maxsize=None, base_mode='grin', crop_mode='square'):
    '''creates hug scene from input which is resized to maxsize
    input: up to 3 (profile) pictures that will be hugged, as PIL.Image
    return: single PIL.Image'''

    assert len(people) <= 3

    image = {'grin': base_grin, 'smile': base_smile}[base_mode].copy()
    align = alignments[len(people)-1]

    for i in range(len(people)):
        person = people[i]

        if crop_mode == 'circle':
            mask = PIL.Image.new('L', person.size, 0)
            PIL.ImageDraw.Draw(mask).ellipse((0, 0) + person.size, fill=255)
            mask = PIL.ImageChops.darker(mask, person.split()[-1])
            person.putalpha(mask)

        # '261' instead of '260' makes the bottom look slightly less 'cut off' after resizing
        person = resize_and_center(person, (align[i][2], align[i][2]))
        image.paste(person, (align[i][0], image.height - 261 + align[i][1]), person)

    image.paste(hand_r, (image.width//2 - hand_r.width - 15, image.height - 260), hand_r)
    image.paste(hand_l, (image.width//2                + 15, image.height - 260), hand_l)

    if maxsize:
        image.thumbnail((maxsize * image.height // 700, maxsize * image.height // 700))

    return image


def draw_text_with_outline(draw, text, corner, fill, font):
    fontsize = round( 50/len(text) * min(10, 4 + len(text)/2) )  # scale to width, but make shorter for short texts
    y = 256 - 15 - round(.65*fontsize) if corner == 'bottom-left' else 15
    font = PIL.ImageFont.truetype(font, fontsize)  # https://www.fontmeme.com/fonts/gilkeynotes-font/

    [draw.text((20+dx, y+dy), text, fill=(0, 0, 0), font=font) for dx in [-1,1] for dy in [-1,1]]  # outline
    draw.text((20, y), text, fill=fill, font=font)


def autographed(people, texts=[' ']):
    image = resize_and_center(people[0], (256, 256))
    draw = PIL.ImageDraw.Draw(image)

    draw_text_with_outline(draw, text=texts[0],           corner='bottom-left', fill=(255, 255, 255), font='GilkeyNotes.ttf')
    draw_text_with_outline(draw, text=(texts + [' '])[1], corner='top-left'   , fill=(255, 255, 255), font='GilkeyNotes.ttf')

    return image


def apply_save(input_fns, func, fn_out='output.png', **kwargs):
    if not issubclass(type(input_fns), list):
        fn_out = input_fns + '.' + func.__name__ + '.png'
        input_fns = [input_fns]

    people = []
    for i in range(len(input_fns[:3])):
        people.append( PIL.Image.open(input_fns[i]).convert('RGBA') )

    func(people, **kwargs).save(fn_out)


def apply_gif_save(input_fns, func, fn_out='output.gif', **kwargs):

    readers = [ imageio.get_reader(input_fn)  for input_fn in input_fns ]
    per_frame_duration = min( reader.get_meta_data().get('duration', 1000)  for reader in readers )
    frames = [ [ PIL.Image.fromarray(data).convert('RGBA') for data in reader ]  for reader in readers ]
    for reader in readers:  reader.close()

    # treat a static image as 1-frame GIF
    # TODO: do better interlacing, maybe with greatest common denominator etc (-> filesize limit?)
    total_frames = min( ( len(sequence) for sequence in frames if len(sequence) ), default=1 )
    frames = [ sequence * total_frames if len(sequence) == 1 else sequence  for sequence in frames ]
    frames = [ func(people, **kwargs)  for people in zip(*frames) ]

    # In case these are actually not animated, save as high-quality PNG and not GIF
    if len(frames) == 1:
        new_fn = fn_out.replace('.gif', '.png')
        frames[0].save(new_fn)
        return new_fn

    # GIFs only support full/no transparency, no alpha channel  :-/
    #   it's also limited to 8-bit (256 colors)
    #   seems like a pretty bad format TBH
    # quality_over_transparency False:  use full transparency, but semi-transparent edges look bad
    # quality_over_transparency True:   mix with discord background color, but no true transparency
    quality_over_transparency = True

    # EXTREMELY HACKY -- consult https://stackoverflow.com/questions/59729587/
    for i in range(len(frames)):

        if quality_over_transparency:
            # https://stackoverflow.com/a/33507138/2111778
            background = PIL.Image.new('RGBA', frames[i].size, (54, 57, 62))  # discord bg color
            frames[i] = PIL.Image.alpha_composite(background, frames[i]).convert('P')
        else:
            frame = frames[i].convert('P')
            p = frame.getpalette()
            frame = numpy.array(frame)
            shiftme = -frame[0][0]
            frame = (frame + shiftme) % 256  # shift data pointing into palette
            frame = PIL.Image.fromarray( frame ).convert('P')
            frame.putpalette( p[-3*shiftme:] + p[:-3*shiftme] )  # shift palette
            frames[i] = frame

    if quality_over_transparency:
        frames[0].save(fn_out, save_all=True, append_images=frames[1:], loop=0, duration=per_frame_duration)
    else:
        frames[0].save(fn_out, save_all=True, append_images=frames[1:], loop=0, duration=per_frame_duration, transparency=0)
        # frames[0].save(fn_out, save_all=True, append_images=frames[1:], loop=0, duration=per_frame_duration, transparency=255, disposal=3)

    return fn_out


if __name__ == '__main__':

    apply_save('0.png', autographed, texts=['Janny♡', 'To: The Dear Reader'])
    apply_save('simp.png', autographed, texts=['The Simp Mage'])

    if len(sys.argv) >= 2:
        person_list = sys.argv[1:]
    else:
        person_list = glob.glob('*.png') + glob.glob('*.jpg')

    for person_fn in person_list:
        if 'hugged' in person_fn or 'emoji' in person_fn:
            continue

        print(person_fn)
        apply_save(person_fn, hugged)
