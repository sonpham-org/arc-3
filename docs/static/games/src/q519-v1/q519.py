"""q519 Reedbed Frame -- build and cross links while controls rotate with a salinity frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,REED,BEETLE,FRAME,LINK,FUNCTION,CROSS,BAD=0,10,14,13,12,9,6,11,15
LEVELS=[
 {"name":"First Causeway","seq":(3,4)},{"name":"Rotated Causeway","seq":(2,1,3,4)},
 {"name":"Two Functions","seq":(1,3,2,1,3,4)},{"name":"Moving Salinity","seq":(2,1,3,2,1,1,3,4)},
 {"name":"Obstructed Route","seq":(1,3,2,1,3,2,1,3,4)},{"name":"Reedbed Frame","seq":(2,1,3,1,2,1,3,2,1,3,4)}]
def core(s,a,x):
 pos,rot,links,function,crossed=s
 if a==1:pos=(pos+(1,2,-1,-2)[rot])%8
 elif a==2:rot=(rot+1)%4
 elif a==3:links^=1<<pos;function=(function+rot+1)%5
 elif a==4:
  if not links&(1<<pos):return None
  pos=(pos+4)%8;function=(function+2)%5;crossed=(pos,links)
 elif a==5:
  if (pos,rot,links,function,crossed)!=x["goal"]:return None
 return pos,rot,links,function,crossed
for x in LEVELS:
 s=(0,0,0,0,None)
 for a in x["seq"]:s=core(s,a,x);assert s is not None
 x["goal"]=s;x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=core(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i in range(8):
   x=8+(i%4)*12;y=8+(i//4)*15;f[y:y+10,x:x+9]=REED
   if g.links&(1<<i):f[y+3:y+7,x:x+12]=LINK
  x=10+(g.pos%4)*12;y=10+(g.pos//4)*15;f[y:y+5,x:x+5]=BEETLE
  f[39:41,8:56]=FRAME;f[41:45,8:8+g.rot*12]=FRAME;f[49:53,8:8+g.function*9]=FUNCTION
  if g.crossed:f[56:60,39:56]=CROSS
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q519(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q519",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=self.rot=self.links=self.function=0;self.crossed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=core((self.pos,self.rot,self.links,self.function,self.crossed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.pos,self.rot,self.links,self.function,self.crossed=s
  elif a==6:
   if (self.pos,self.rot,self.links,self.function,self.crossed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
