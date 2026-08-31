"""a049 Bottleneck Bins -- meter a branching finite-capacity flow."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FACTORY,PIPE,BIN_A,BIN_B,BIN_C,ITEM,GATE,FLOW,BAD=9,8,4,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Feed Source","seq":(1,)},{"name":"Open Branch","seq":(1,2)},
 {"name":"Drain First","seq":(1,2,4)},{"name":"Backpressure","seq":(1,1,2,3,4)},
 {"name":"Meter Releases","seq":(1,2,1,3,4,2,4)},{"name":"Bottleneck Bins","seq":(1,1,2,3,4,1,2,4,3)},
]
def advance(s,a):
 bins,gates,source,spill,trace,snapshot=s;b=list(bins);ga=list(gates)
 if a==1:
  if b[0]<3:b[0]+=1
  else:source=min(4,source+1)
  trace=(trace+(1,))[-8:]
 elif a==2:
  ga[0]^=1
  if ga[0] and b[0] and b[1]<4:b[0]-=1;b[1]+=1
  elif ga[0] and b[0]:spill=(spill+1)%5
  trace=(trace+(2,))[-8:]
 elif a==3:
  ga[1]^=1
  if ga[1] and b[0] and b[2]<2:b[0]-=1;b[2]+=1
  elif ga[1] and b[0]:spill=(spill+1)%5
  trace=(trace+(3,))[-8:]
 elif a==4:
  if b[1]:b[1]-=1
  elif b[2]:b[2]-=1
  elif source and b[0]<3:source-=1;b[0]+=1
  trace=(trace+(4,))[-8:]
 elif a==5:snapshot=(tuple(b),tuple(ga),source,spill,trace)
 return tuple(b),tuple(ga),source,spill,trace,snapshot
for x in LEVELS:
 s=((0,0,0),(0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FACTORY
  f[10:17,6:28]=PIPE;f[26:33,26:51]=PIPE;f[42:49,26:51]=PIPE
  boxes=((8,18,25,38,BIN_A),(36,19,56,35,BIN_B),(36,39,56,54,BIN_C))
  for i,(x1,y1,x2,y2,col) in enumerate(boxes):
   f[y1:y2,x1:x2]=col
   for j in range(g.bins[i]):f[y2-4-j*4:y2-1-j*4,x1+3:x2-3]=ITEM
  f[24:36,29:34]=GATE if g.gates[0] else PIPE;f[40:52,29:34]=GATE if g.gates[1] else PIPE
  for i in range(g.source):f[7:11,8+i*5:12+i*5]=ITEM
  for i in range(g.spill):f[55:58,8+i*6:13+i*6]=BAD
  for i,v in enumerate(g.trace[-8:]):f[55:58,32+i*3:34+i*3]=FLOW
  if g.bad:f[1:4,18:46]=BAD
  return f
class A049(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a049",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins,self.gates,self.source,self.spill,self.trace,self.snapshot=((0,0,0),(0,0),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.gates,self.source,self.spill,self.trace,self.snapshot=advance((self.bins,self.gates,self.source,self.spill,self.trace,self.snapshot),a)
  elif a==6:
   if (self.bins,self.gates,self.source,self.spill,self.trace,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
