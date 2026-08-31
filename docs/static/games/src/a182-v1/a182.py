"""a182 Minimal Obstruction -- delete every node unnecessary to network failure."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,NETWORK,NODE_A,NODE_B,EDGE,REMOVED,CRITICAL,CURSOR,FAILURE,EXCESS=3,8,12,14,9,7,4,13,6,11
BAD=15
CORE=0b00101101
LEVELS=[
 {"name":"Remove Node","seq":(1,)},{"name":"Select Node","seq":(2,)},
 {"name":"Probe Failure","seq":(3,1)},{"name":"Test Necessity","seq":(1,2,3,4,2)},
 {"name":"Delete Irrelevant","seq":(1,3,2,1,4,3,2)},{"name":"Minimal Obstruction","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 active,cursor,probe,failure,critical,excess,history,snapshot=s
 if a==1:active^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:probe=(probe+1)%4;history=(history+(3,))[-8:]
 elif a==4:failure=int((active&CORE)==CORE);critical=(active&CORE).bit_count();excess=(active&~CORE).bit_count();history=(history+(4,))[-8:]
 elif a==5:snapshot=(active,cursor,probe,failure,critical,excess,history)
 return active,cursor,probe,failure,critical,excess,history,snapshot
for q in LEVELS:
 s=((1<<8)-1,0,0,1,4,4,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=NETWORK;pts=((31,8),(47,15),(55,31),(47,47),(31,55),(15,47),(7,31),(15,15))
  for i,(x,y) in enumerate(pts):
   col=REMOVED if not((g.active>>i)&1) else CRITICAL if (CORE>>i)&1 else NODE_A if i%2==0 else NODE_B;f[y-5:y+6,x-5:x+6]=col
   if i==g.cursor:f[y-8:y-6,x-6:x+7]=CURSOR
  f[54:58,8:28]=FAILURE if g.failure else BAD;f[54:58,31:31+g.critical*5]=CRITICAL;f[7:10,8:8+g.excess*9]=EXCESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A182(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a182",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.active,self.cursor,self.probe,self.failure,self.critical,self.excess,self.history,self.snapshot=((1<<8)-1,0,0,1,4,4,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.active,self.cursor,self.probe,self.failure,self.critical,self.excess,self.history,self.snapshot=advance((self.active,self.cursor,self.probe,self.failure,self.critical,self.excess,self.history,self.snapshot),a)
  elif a==6:
   if (self.active,self.cursor,self.probe,self.failure,self.critical,self.excess,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
