"""q564 Honeycomb Counter -- shape a legible rival across nested apiary clocks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,NECTAR,RIVAL,LOCAL,OUTER,SHAPE,HARVEST,BAD=11,4,6,2,8,9,13,3,10,15
LEVELS=[
 {"name":"Visible Reply","cycle":3,"need":0,"plan":(1,5)},
 {"name":"Shape Once","cycle":3,"need":1,"plan":(1,2,5)},
 {"name":"Three Tactics","cycle":3,"need":2,"plan":(1,2,3,5)},
 {"name":"Outer Turn","cycle":2,"need":1,"plan":(4,4,1,2,5)},
 {"name":"Nested Treatment","cycle":3,"need":2,"plan":(1,4,2,4,3,4,5)},
 {"name":"Honeycomb Counter","cycle":3,"need":3,"plan":(1,2,4,3,4,1,4,2,5)}]
def advance(s,a,x):
 history,opponent,local,outer,nectar,shaped,harvested=s;history=list(history)
 if a in (1,2,3):
  t=a-1;old=opponent
  if history and history[-1]!=t:shaped+=1
  history=(history+[t])[-3:];nectar+=int(t==(old+1)%3);opponent=(sum(history)+outer+len(history))%3
 elif a==4:
  local+=1
  if local==x["cycle"]:local=0;outer=(outer+1)%4
 elif a==5:
  if shaped<x["need"]:return None
  harvested=(nectar,opponent,local,outer,tuple(history),shaped)
 return tuple(history),opponent,local,outer,nectar,shaped,harvested
def target(x):
 s=((),0,0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HIVE
  for yi,y in enumerate((8,20,32)):
   for xi,x in enumerate((8,20,32,44)):f[y:y+8,x:x+10]=CELL+(xi+yi)%2
  for i,t in enumerate(g.history):f[10+i*12:16+i*12,10+t*14:18+t*14]=NECTAR+t
  f[45:50,8:16+g.opponent*13]=RIVAL;f[52:55,8:8+g.local*12]=LOCAL;f[56:59,8:8+g.outer*10]=OUTER
  f[2:4,6:6+g.shaped*8]=SHAPE
  if g.harvested:f[40:44,43:56]=HARVEST
  if g.bad:f[61:64,18:46]=BAD
  return f
class Q564(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q564",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.history=();self.opponent=self.local=self.outer=self.nectar=self.shaped=0;self.harvested=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.history,self.opponent,self.local,self.outer,self.nectar,self.shaped,self.harvested),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.history,self.opponent,self.local,self.outer,self.nectar,self.shaped,self.harvested=s
  elif a==6:
   if (self.history,self.opponent,self.local,self.outer,self.nectar,self.shaped,self.harvested)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
