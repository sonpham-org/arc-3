"""q616 Crossing Grammar -- compose disjoint controller messages through persistent ferry marks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,GLYPH0,GLYPH1,GLYPH2,DOCK,MARK0,MARK1,GROUP,CODE,BAD=3,4,10,11,12,14,6,7,9,13,15
LEVELS=[
 {"name":"First Mark","seq":(1,2,4)},{"name":"Reverse Message","seq":(2,1,4)},
 {"name":"Two Controllers","seq":(1,4,3,2,4)},{"name":"Grouped Crossing","seq":(1,2,4,3,2,1,4)},
 {"name":"Persistent Syntax","seq":(1,4,3,2,2,4,3,1,4)},
 {"name":"Crossing Grammar","seq":(2,1,4,3,1,2,4,3,2,2,4)}]
def advance(s,a):
 controller,buf,marks,code=s;buf=list(buf)
 if a in (1,2):buf.append(((a-1)+controller)%3)
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,tuple(buf),(sum(buf)+controller)%3),);buf=[]
 elif a==5:
  if not marks or buf:return None
  code=(sum((i+1)*(m[2]+m[0]) for i,m in enumerate(marks))+controller)%6
 return controller,tuple(buf),marks,code
for x in LEVELS:
 s=(0,(),(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,(),(),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;cols=(GLYPH0,GLYPH1,GLYPH2)
  for i in range(6):x=8+i*9;f[9:14,x:x+6]=cols[(i+g.controller)%3];f[18:21,x:x+7]=DOCK
  for i,v in enumerate(g.buf[-6:]):f[27:38,8+i*9:15+i*9]=cols[v]
  for i,m in enumerate(g.marks[-5:]):f[43:48,8+i*10:15+i*10]=MARK0 if m[0]==0 else MARK1
  f[52:56,8:28]=MARK0 if g.controller==0 else MARK1
  if g.marks:f[56:60,31:42]=GROUP
  if g.code is not None:f[55:59,43:56]=CODE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q616(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q616",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.buf=();self.marks=();self.code=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.buf,self.marks,self.code),a)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.buf,self.marks,self.code=s
  elif a==6:
   if (self.controller,self.buf,self.marks,self.code)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
