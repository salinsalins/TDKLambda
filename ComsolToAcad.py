import time
from pyautocad import Autocad, APoint
import ezdxf


# acad = Autocad()
# acad.prompt("Hello, Autocad from Python\n")
# print(acad.doc.Name)

data_file_name = "d:\Your files\Sanin\Documents\COMSOL\SIBA3 and Crocodile\Толстое кольцо\Trajectories.txt"
data_file_name = "d:\Particles_2.txt"
dxf_file_name = data_file_name.replace('txt', 'dxf')


print('Processing data file', data_file_name)
print('')
t0 = time.time()
t1 = time.time()
data = {}
titles = []
parameters = {}
n = 0
with open(data_file_name) as f:
    while True:
        line = f.readline()
        # print(line)
        if len(line) <= 0:
            break
        # if line.startswith('% x'):
        #     splitted = line.split(' ')
        #     for s in splitted[1:]:
        #         key = s.strip()
        #         if len(key) > 0:
        #             titles.append(key)
        #             data[key] = []
        #     continue
        if line.startswith('%'):
            if line.find(':') >= 0:
                splitted = line.split(':')
                key = splitted[0][2:].strip()
                value = splitted[1].strip()
                parameters[key] = value
                print(key, ':', value)
            else:
                if len(titles) <= 0:
                    splitted = line.split(' ')
                    for s in splitted[1:]:
                        key = s.strip()
                        if len(key) > 0:
                            titles.append(key)
                            data[key] = []
                    print('Columns:', titles)
            continue
        splitted = line.split(' ')
        i = 0
        for s in splitted:
            ss = s.strip()
            if len(ss) > 0:
                try:
                    value = float(ss)
                except:
                    value = float('nan')
                    print('Wrong data format')
                key = titles[i]
                data[key].append(value)
                i += 1
        if (time.time() - t1) > 1:
            t1 = time.time()
            print('Processing line', n, line)
        n += 1
print('Processed', len(data[titles[0]]), 'rows in %6.1f' % (time.time() - t0), 'seconds')

print('Generating GXF file', dxf_file_name)
drawing = ezdxf.new(dxfversion='AC1024')
modelspace = drawing.modelspace()
modelspace.add_line((0, 0), (10, 0), dxfattribs={'color': 7})
#drawing.layers.create('TEXTLAYER', dxfattribs={'color': 2})
#modelspace.add_text('Test', dxfattribs={'insert': (0, 0.2), 'layer': 'TEXTLAYER'})
x0 = 8320.18
x0 = 91.5
y0 = -3537.64 - 4.13
y0 = 342.3
p1 = (0, 0)
particle = -1
total = len(data['x'])
t0 = time.time()
for i in range(total):
    x = data['z'][i] + x0
    y = data['x'][i] + y0
    p2 = (x, y)
    if data['Particle'][i] == particle:
        modelspace.add_line(p1, p2, dxfattribs={'color': 7})
    else:
        particle = data['Particle'][i]
    p1 = p2
    # if percents % 10 == 0:
    if (time.time() - t0) > 1:
        t0 = time.time()
        percents = i*100/total
        print('Completed %5.2f' % percents, '%')
print('Completed', 100, '%')

drawing.saveas(dxf_file_name)


# x0 = 8320.18
# y0 = -3537.64 - 4.13
# p1 = APoint(0, 0)
# particle = -1
# total = len(data['x'])
# for i in range(total):
#     if (i*100/total+1) % 10 == 0:
#         print('Completed', i*100/total, '%')
#     x = data['z'][i] + x0
#     y = data['x'][i] + y0
#     p2 = APoint(x, y)
#     if data['Particle'][i] == particle:
#         acad.model.AddLine(p1, p2)
#     else:
#         particle = data['Particle'][i]
#     p1 = p2
#
# #
# # p1 = APoint(0, 0)
# # p2 = APoint(50, 25)
# # for i in range(5):
# #     #text = acad.model.AddText('Hi %s!' % i, p1, 2.5)
# #     acad.model.AddLine(p1, p2)
# #     #acad.model.AddCircle(p1, 10)
# #     p1.y += 10
# #
# # dp = APoint(10, 0)
# #
# # #for text in acad.iter_objects('Text'):
# # #    print('text: %s at: %s' % (text.TextString, text.InsertionPoint))
# # #    text.InsertionPoint = APoint(text.InsertionPoint) + dp
# #
# # #for obj in acad.iter_objects(['Circle', 'Line']):
# # #    print(obj.ObjectName)
# #
