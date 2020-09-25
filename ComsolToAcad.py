from pyautocad import Autocad, APoint


acad = Autocad()
acad.prompt("Hello, Autocad from Python\n")
print(acad.doc.Name)

file_name = "d:\Your files\Sanin\Documents\COMSOL\SIBA3 and Crocodile\Толстое кольцо\Trajectories.txt"


data = {}
titles = []
parameters = {}
with open(file_name) as f:
    while True:
        line = f.readline()
        # print(line)
        if len(line) <= 0:
            break
        if line.startswith('% x'):
            splitted = line.split(' ')
            for s in splitted[1:]:
                key = s.strip()
                if len(key) > 0:
                    titles.append(key)
                    data[key] = []
            continue
        if line.startswith('%'):
            if line.find(':') >= 0:
                splitted = line.split(':')
                key = splitted[0][2:].strip()
                value = splitted[1].strip()
                parameters[key] = value
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
print('Columns:', titles, 'Rows:', len(data[titles[0]]))


# import ezdxf
# drawing = ezdxf.new(dxfversion='AC1024')
# modelspace = drawing.modelspace()
# modelspace.add_line((0, 0), (10, 0), dxfattribs={'color': 7})
# #drawing.layers.create('TEXTLAYER', dxfattribs={'color': 2})
# #modelspace.add_text('Test', dxfattribs={'insert': (0, 0.2), 'layer': 'TEXTLAYER'})
# p1 = (0, 0)
# particle = -1
# total = len(data['x'])
# for i in range(total):
#     if (i*100/total+1) % 10 == 0:
#         print('Completed', i*100/total, '%')
#     x = data['z'][i]
#     y = data['x'][i]
#     p2 = (x, y)
#     if data['Particle'][i] == particle:
#         modelspace.add_line(p1, p2, dxfattribs={'color': 7})
#     else:
#         particle = data['Particle'][i]
#     p1 = p2
# drawing.saveas('test.dxf')



x0 = 8320.18
y0 = -3537.64 - 4.13
p1 = APoint(0, 0)
particle = -1
total = len(data['x'])
for i in range(total):
    if (i*100/total+1) % 10 == 0:
        print('Completed', i*100/total, '%')
    x = data['z'][i] + x0
    y = data['x'][i] + y0
    p2 = APoint(x, y)
    if data['Particle'][i] == particle:
        acad.model.AddLine(p1, p2)
    else:
        particle = data['Particle'][i]
    p1 = p2
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
