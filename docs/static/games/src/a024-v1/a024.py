"""a024 Crosswind Calibration -- separate actuator motion from additive drift."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SHELTER,WIND,TRAVELER,FLAG,TRACE,GOAL,BAD=3,10,8,12,14,11,6,13,15
LEVELS=[{"name":"Sheltered Move","seq":(1,3)},{"name":"Wind Exposed","seq":(2,3)},{"name":"Drift Contrast","seq":(1,2,3)},{"name":"Changed Wind","seq":(4,2,1,3)},{"name":"Closed Loop","seq":(2,3,1,4,2,1,3)},{"name":"Crosswind Calibration","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pos,drift,sheltered,traces,flags,reached=s;x,y=pos
 if a in (1,2):
  dx,dy=((1,0) if a==1 else (0,1));wx,wy=(0,0) if sheltered else drift;x=(x+dx+wx)%8;y=(y+dy+wy)%8
 elif a==3:traces=traces+((pos,(x,y),drift,sheltered),);flags=flags+(((x+drift[0])%8,(y+drift[1])%8),)
 elif a==4:drift=(drift[1],-drift[0]);sheltered=not sheltered
 elif a==5:reached=((x,y),drift,sheltered,traces[-4:],flags[-4:])
 return (x,y),drift,sheltered,traces,flags,reached
for x in LEVELS:
 s=((1,1),(1,-1),True,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;f[6:19,6:58]=SHELTER
  for y in range(8):
   for x in range(8):f[7+y*6:12+y*6,7+x*6:12+x*6]=SHELTER if y<2 else FIELD
  x,y=g.pos;f[7+y*6:12+y*6,7+x*6:12+x*6]=TRAVELER
  for x,y in g.flags[-4:]:f[7+y*6:12+y*6,7+x*6:12+x*6]=FLAG
  for i,_ in enumerate(g.traces[-3:]):f[55:59,8+i*14:18+i*14]=TRACE
  f[1:4,8:28]=WIND
  if g.reached:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A024(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a024",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=(1,1);self.drift=(1,-1);self.sheltered=True;self.traces=self.flags=();self.reached=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.drift,self.sheltered,self.traces,self.flags,self.reached=advance((self.pos,self.drift,self.sheltered,self.traces,self.flags,self.reached),a)
  elif a==6:
   if (self.pos,self.drift,self.sheltered,self.traces,self.flags,self.reached)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
