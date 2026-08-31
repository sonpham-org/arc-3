"""q526 Crossing Frame -- compose ferry motion across controllers with persistent handoff marks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,DOCK,FERRY,PASSENGER,FRAME,MARK0,MARK1,GOAL,BAD=0,9,11,14,12,6,10,7,13,15
LEVELS=[
 {"name":"First Passenger","seq":(1,)},{"name":"Dock Frame","seq":(2,1)},
 {"name":"Marked Handoff","seq":(1,4,3,1)},{"name":"Two Controllers","seq":(2,4,3,1,4,3,1)},
 {"name":"Capacity Crossing","seq":(1,2,4,3,1,2,4,3,1)},
 {"name":"Crossing Frame","seq":(2,1,4,3,2,1,4,3,1,2,4,3,1)}]
def advance(s,a):
 controller,pos,dock,frame,marks,load,locked=s
 if a==1:
  if controller==0:pos=(pos+(1 if frame%2==0 else -1))%8
  else:dock=(dock+1+frame)%3
  load=(load+1)%5
 elif a==2:frame=(frame+1)%4;dock=(dock+controller)%3
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,pos,dock,frame,load),)
 elif a==5:locked=(controller,pos,dock,frame,marks,load)
 return controller,pos,dock,frame,marks,load,locked
for x in LEVELS:
 s=(0,0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,0,0,(),0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i in range(3):x=8+i*18;f[9:25,x:x+14]=DOCK if i!=g.dock else FERRY
  for i in range(8):x=9+i*6;f[30:36,x:x+4]=PASSENGER if i==g.pos else FRAME
  f[40:44,8:8+g.frame*11+8]=FRAME
  for i,m in enumerate(g.marks[-5:]):f[49:54,8+i*10:15+i*10]=MARK0 if m[0]==0 else MARK1
  f[56:60,8:8+g.load*9]=PASSENGER
  if g.locked:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q526(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q526",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=self.pos=self.dock=self.frame=self.load=0;self.marks=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.pos,self.dock,self.frame,self.marks,self.load,self.locked),a)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.pos,self.dock,self.frame,self.marks,self.load,self.locked=s
  elif a==6:
   if (self.controller,self.pos,self.dock,self.frame,self.marks,self.load,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
