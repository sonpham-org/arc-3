"""a195 Interface Adapter -- chain converters across shape, direction, and pulse conventions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BENCH,SENSOR,ACTUATOR,ADAPTER_A,ADAPTER_B,ADAPTER_C,CURSOR,COMPATIBLE,GAP=4,1,12,14,10,8,5,13,7,6
BAD=15
TARGET=(1,3,0,2,1)
LEVELS=[
 {"name":"Choose Adapter","seq":(1,)},{"name":"Move Socket","seq":(2,)},
 {"name":"Reverse Direction","seq":(3,1)},{"name":"Check Interfaces","seq":(1,2,3,4,2)},
 {"name":"Minimal Chain","seq":(1,3,2,1,4,3,2)},{"name":"Interface Adapter","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 chain,cursor,direction,compatible,gaps,history,snapshot=s;c=list(chain)
 if a==1:c[cursor]=(c[cursor]+1)%4;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:direction=1-direction;c.reverse();cursor=4-cursor;history=(history+(3,))[-8:]
 elif a==4:compatible=sum(int(c[i]==TARGET[(i+direction)%5]) for i in range(5));gaps=5-compatible;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(c),cursor,direction,compatible,gaps,history)
 return tuple(c),cursor,direction,compatible,gaps,history,snapshot
for q in LEVELS:
 s=((1,3,0,2,1),0,0,5,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BENCH;f[24:42,6:14]=SENSOR;f[24:42,50:58]=ACTUATOR
  cols=(ADAPTER_A,ADAPTER_B,ADAPTER_C,SENSOR)
  for i,v in enumerate(g.chain):
   x=15+i*7;f[26:40,x:x+6]=cols[v];f[21:25,x+1:x+5]=COMPATIBLE if v==TARGET[(i+g.direction)%5] else GAP
   if i==g.cursor:f[42:46,x:x+6]=CURSOR
  f[49:53,8:8+g.compatible*8]=COMPATIBLE;f[54:58,8:8+g.gaps*8]=GAP
  if g.bad:f[1:4,18:46]=BAD
  return f
class A195(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a195",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.chain,self.cursor,self.direction,self.compatible,self.gaps,self.history,self.snapshot=((1,3,0,2,1),0,0,5,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.chain,self.cursor,self.direction,self.compatible,self.gaps,self.history,self.snapshot=advance((self.chain,self.cursor,self.direction,self.compatible,self.gaps,self.history,self.snapshot),a)
  elif a==6:
   if (self.chain,self.cursor,self.direction,self.compatible,self.gaps,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
