import bpy
import json
from math import sqrt
import requests
import re

# Replace this with your own funda URL
url = 'https://www.funda.nl/koop/zeewolde/huis-42126150-cumulus-72/'

funda_response = requests.get(url, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'})
fml_matches = re.findall('"[^"]*\\.fml"', str(funda_response.content))
if len(fml_matches) == 0:
  raise Exception('No .fml files found on Funda link')
fml_url = fml_matches[0][1:-1]
fml_response = requests.get(fml_url)

data = json.loads(fml_response.content)

def normalise(p):
  (x, y) = p
  length = sqrt(x*x + y*y)
  return (x/length, y/length)

def normalise3(p):
  (x, y, z) = p
  length = sqrt(x*x + y*y + z*z)
  return (x/length, y/length, z/length)

def distance(p1, p2):
  (x1, y1) = p1
  (x2, y2) = p2
  return sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

def multiply(v, p):
  (x, y) = p
  return (x * v, y * v)

def multiply3(v, p):
  (x, y, z) = p
  return (x * v, y * v, z * v)

def add(p1, p2):
  (x1, y1), (x2, y2) = (p1, p2)
  return (x1 + x2, y1 + y2)

def add3(p1, p2):
  (x1, y1, z1), (x2, y2, z2) = (p1, p2)
  return (x1 + x2, y1 + y2, z1 + z2)

def subtract3(p1, p2):
  (x1, y1, z1), (x2, y2, z2) = (p1, p2)
  return (x1 - x2, y1 - y2, z1 - z2)

def dot3(p1, p2):
  (x1, y1, z1) = p1
  (x2, y2, z2) = p2
  return x1 * x2 + y1 * y2 + z1 * z2

def is_between(v1, v2, v3):
  return min(v2, v3) <= v1 <= max(v2, v3)

def is_in_box3(p, b):
  (p1, p2, p3, p4) = b
  u = subtract3(p1, p2)
  v = subtract3(p1, p3)
  w = subtract3(p1, p4)
  return is_between(dot3(u, p), dot3(u, p1), dot3(u, p2)) and is_between(dot3(v, p), dot3(v, p1), dot3(v, p3)) and is_between(dot3(w, p), dot3(w, p1), dot3(w, p4))

def create_object (name, vertices, edges, faces):
  mesh = bpy.data.meshes.new(name)
  mesh.from_pydata(vertices, edges, faces)
  mesh.update()
  return bpy.data.objects.new(name, mesh)

def create_wall(w, col):
  if w['c'] != None:
    create_curved_wall(w, col)
    return
  name = 'wall'
  (ax, ay, az, ah) = (-w['a']['x']/100, w['a']['y']/100, w['az']['z']/100, w['az']['h']/100)
  (bx, by, bz, bh) = (-w['b']['x']/100, w['b']['y']/100, w['bz']['z']/100, w['bz']['h']/100)
  thickness = w['thickness']/100
  d = normalise((bx - ax, by - ay))
  (dx, dy) = d
  x_points = [(ax, ay)]
  # This algorithm will probably cause problems for vertically diagonal walls.
  y_points = {az, ah, bz, bh}
  opening_boxes = []

  openings = w['openings']
  openings.sort(key = lambda o: o['t'])
  n3 = (-dy, dx, 0)
  for o in openings:
    center_point = add((ax, ay), multiply(o['t'], (bx - ax, by - ay)))
    new_x_points = [add(center_point, multiply(o['width']/200 * dir, d)) for dir in [-1, 1]]
    x_points.extend(new_x_points)
    new_y_points = [o['z'] / 100, o['z'] / 100 + o['z_height'] / 100]
    y_points = y_points.union(new_y_points)
    p1 = add3((new_x_points[0][0], new_x_points[0][1], new_y_points[0]), multiply3(0.5 * thickness, n3))
    p2 = add3((new_x_points[1][0], new_x_points[1][1], new_y_points[0]), multiply3(0.5 * thickness, n3))
    p3 = add3((new_x_points[0][0], new_x_points[0][1], new_y_points[0]), multiply3(-0.5 * thickness, n3))
    p4 = add3((new_x_points[0][0], new_x_points[0][1], new_y_points[1]), multiply3(0.5 * thickness, n3))
    opening_boxes.append((p1, p2, p3, p4))
  x_points.append((bx, by))
  y_points = sorted(y_points)

  point_count = len(y_points) * 2
  vertices = []
  edges = []
  faces = []

  for i in range(len(x_points)):
    xi,yi = x_points[i]
    def get_side(dir):
      return [(xi + dir * 0.5 * thickness * -dy, yi + dir * 0.5 * thickness * dx, y) for y in y_points]
    new_vertices = get_side(1) + list(reversed(get_side(-1)))
    vertices.extend(new_vertices)
    edges.append(((i + 1) * point_count - 1, i * point_count))
    for j in range(point_count):
      base_index = i * point_count + j
      v_diff = int(point_count - 1 - 2*j)
      if j > 0:
        edges.append((base_index, base_index - 1))
      if i > 0:
        edges.append((base_index - point_count, base_index))
        if j > 0:
          if i == len(x_points) - 1:
            faces.append([base_index, base_index - 1, base_index + v_diff + 1, base_index + v_diff])

          p1 = vertices[base_index]
          p2 = vertices[base_index - 1 - point_count]
          center_point = add3(p1, multiply3(0.5, subtract3(p2, p1)))
          if not any(is_in_box3(center_point, box) for box in opening_boxes):
            faces.append([base_index, base_index - 1, base_index - 1 - point_count, base_index - point_count])
          elif j <= point_count / 2:
            
            faces.append([base_index, base_index - 1, base_index + 1 + v_diff, base_index + v_diff])
            faces.append([base_index, base_index - point_count, base_index + v_diff - point_count, base_index + v_diff])
            faces.append([base_index - 1, base_index - point_count - 1, base_index - point_count + 1 + v_diff, base_index + v_diff + 1])
            faces.append([base_index - point_count, base_index - point_count - 1, base_index - point_count + 1 + v_diff, base_index - point_count + v_diff])
        else:
          faces.append([base_index, base_index - point_count, base_index - point_count + v_diff, base_index + v_diff])
      elif j > 0:
        faces.append([base_index, base_index - 1, base_index + v_diff + 1, base_index + v_diff])

  obj = create_object('wall', vertices, edges, faces)
  col.objects.link(obj) 
  
def linear_bezier(t, p0, p1):
  return add(multiply(1-t, p0), multiply(t, p1))

def quadratic_bezier(t, p0, p1, p2):
  return add(multiply(1-t, linear_bezier(t, p0, p1)), multiply(t, linear_bezier(t, p1, p2)))

def find_opening_t(t, p0, p1, p2, width, delta):
  center = quadratic_bezier(t, p0, p1, p2)
  goal_width = width / 2.4
  new_t = t
  length = 0
  previous_point = center
  while True:
    new_t += delta
    if new_t >= 1:
      return 1
    if new_t <= 0:
      return 0
    new_point = quadratic_bezier(new_t, p0, p1, p2)
    distance_from_previous = distance(previous_point, new_point)
    length += distance_from_previous
    previous_point = new_point
    if length >= goal_width:
      return new_t
    
def within_opening(i1, j1, t_values, y_values, openings2d):
  if i1 <= 0 or j1 <= 0 or i1 >= len(t_values) or j1 >= len(y_values):
    return True
  midx, midy = (t_values[i1-1] + (t_values[i1] - t_values[i1-1]) / 2, y_values[j1-1] + (y_values[j1] - y_values[j1-1]) / 2)
  return any(minx <= midx <= maxx and miny <= midy <= maxy for ((minx,miny), (maxx, maxy)) in openings2d)

def create_curved_wall(w, col):
  (ax, ay, az, ah) = (-w['a']['x']/100, w['a']['y']/100, w['az']['z']/100, w['az']['h']/100)
  (bx, by) = (-w['b']['x']/100, w['b']['y']/100)
  (cx, cy) = (-w['c']['x']/100, w['c']['y']/100)
  thickness = w['thickness']/100
  vertices = []
  edges = []
  faces = []
  steps_count = 64
  p0 = (ax, ay)
  p1 = (cx, cy)
  p2 = (bx, by)
  t_values = {i / (steps_count - 1) for i in range(steps_count)}
  y_values = {az, az + ah}
  openings = w['openings']
  openings.sort(key = lambda o: o['t'])
  openings2d = []
  for o in openings:
    t = o['t']
    lowest = o['z']/100
    highest = lowest + o['z_height']/100
    y_values.add(lowest)
    y_values.add(highest)
    width = o['width'] / 100
    t1 = find_opening_t(t, p0, p1, p2, width, 0.001)
    t2 = find_opening_t(t, p0, p1, p2, width, -0.001)
    t_values.add(t1)
    t_values.add(t2)
    openings2d.append(((min(t1, t2), lowest), (max(t1, t2), highest)))

  t_values = sorted(t_values)
  y_values = sorted(y_values)
  point_count = len(y_values) * 2
  for i in range(len(t_values)):
    t = t_values[i]
    dir_p0 = linear_bezier(t, p0, p1)
    dir_p1 = linear_bezier(t, p1, p2)
    direction = normalise(add(dir_p1, (-dir_p0[0], -dir_p0[1])))
    p = add(multiply(1-t, dir_p0), multiply(t, dir_p1))
    normal = (-direction[1], direction[0])
    
    def get_side(dir):
      return [(x, y, z) for ((x, y),z) in [(add(p, multiply(0.5 * thickness * dir, normal)), z) for z in y_values]]
    new_vertices = get_side(1) + list(reversed(get_side(-1)))
    vertices.extend(new_vertices)


    for j in range(point_count):
      base_index = i * point_count + j
      if j == 0:
        edges.append((base_index, base_index + point_count - 1))
      else:
        if not within_opening(i-1, j, t_values, y_values, openings2d) and not within_opening(i, j, t_values, y_values, openings2d):
          edges.append((base_index, base_index - 1))
      if i > 0:
        edges.append((base_index, base_index - point_count))
      if 0 < j < point_count / 2 and i > 0:
        v_diff = int(point_count - 1 - 2*j)
        is_open = within_opening(i, j, t_values, y_values, openings2d)
        if not is_open:
          faces.append([base_index, base_index - 1, base_index - point_count - 1, base_index - point_count])
          faces.append([base_index + v_diff, base_index + v_diff + 1, base_index + v_diff + 1 - point_count, base_index + v_diff - point_count])
        if (is_open and not within_opening(i-1, j, t_values, y_values, openings2d)) or i == 1:
          faces.append([base_index - point_count, base_index - point_count - 1, base_index - point_count + v_diff + 1, base_index - point_count + v_diff])
        if (is_open and not within_opening(i+1, j, t_values, y_values, openings2d)) or i == len(t_values) - 1:
          faces.append([base_index, base_index - 1, base_index + v_diff + 1, base_index + v_diff])
        if (is_open and not within_opening(i, j-1, t_values, y_values, openings2d)) or j == 1:
          faces.append([base_index - 1, base_index + v_diff + 1, base_index + v_diff + 1 - point_count, base_index - 1 - point_count])
        if (is_open and not within_opening(i, j+1, t_values, y_values, openings2d)) or j == point_count / 2 - 1:
          faces.append([base_index, base_index + v_diff, base_index + v_diff - point_count, base_index - point_count])

  obj = create_object('curved_wall', vertices, edges, faces)
  col.objects.link(obj) 

def create_area(a, col):
  name = 'area'
  if 'name' in a:
    name = a['name']
  vertices = [(-p['x']/100, p['y']/100, p['z']/100) for p in a['poly']]
  edges = [(x,x+1) for x in range(len(vertices) - 1)] + [(len(vertices)-1,0)]
  faces = [[i for i in range(len(vertices))]]
  obj = create_object(name, vertices, edges, faces)
  col.objects.link(obj)

for floor in data['floors']:
  for di in range(len(floor['designs'])):
    name = floor['name'] + '-design-' + str(di)
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    wc = bpy.data.collections.new('Walls')
    fc = bpy.data.collections.new('Floors')
    c.children.link(wc)
    c.children.link(fc)
    design = floor['designs'][di]
    for a in design['areas']:
      create_area(a, fc)
    for w in design['walls']:
      create_wall(w, wc)
