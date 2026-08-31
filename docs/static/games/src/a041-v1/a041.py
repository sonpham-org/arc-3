"""a041 Race Gate -- order two autonomous carriers around shared switches."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GROUND,TRACK,CAR_A,CAR_B,SWITCH,GATE,TRACE,BAD=1,9,8,12,14,10,13,6,15
LEVELS=[
 {"name":"First Arrival","seq":(1,)},
 {"name":"Yield Once","seq":(2,1)},
 {"name":"Reverse Priority","seq":(4,1,3)},
 {"name":"Shared Tick","seq":(1,2,1,3)},
 {"name":"Safe Interleave","seq":(2,1,4,3,1,2)},
 {"name":"Race Gate","seq":(1,3,2,4,1,2,3,1,4)},
]
def advance(s,a):
 pa,pb,sa,sb,da,db,priority,gate,trace,latch=s
 if a==1:
  if priority==0:pa=(pa+1+da)%8;sa^=int(pa in (2,6));pb=(pb+1+db)%8;sb^=int(pb in (1,5))
  else:pb=(pb+1+db)%8;sb^=int(pb in (1,5));pa=(pa+1+da)%8;sa^=int(pa in (2,6))
  gate=int(sa==sb==1);trace=(trace+(priority,))[-8:]
 elif a==2:da^=1;trace=(trace+(2,))[-8:]
 elif a==3:db^=1;trace=(trace+(3,))[-8:]
 elif a==4:priority^=1;trace=(trace+(4,))[-8:]
 elif a==5:latch=(pa,pb,sa,sb,da,db,priority,gate,trace)
 return pa,pb,sa,sb,da,db,priority,gate,trace,latch
for x in LEVELS:
 s=(0,7,0,0,0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GROUND;f[16:22,7:57]=TRACK;f[39:45,7:57]=TRACK
  for x in (20,44):f[12:26,x:x+3]=SWITCH
  for x in (14,38):f[35:49,x:x+3]=SWITCH
  xa=8+g.pa*6;xb=8+g.pb*6;f[13:25,xa:xa+5]=CAR_A;f[36:48,xb:xb+5]=CAR_B
  f[7:14,51:58]=GATE if g.gate else BAD
  f[52:57,8:24]=CAR_A if g.priority==0 else CAR_B
  for i,v in enumerate(g.trace[-8:]):f[53:57,28+i*3:30+i*3]=TRACE if v in (0,1) else SWITCH
  if g.bad:f[1:4,18:46]=BAD
  return f
class A041(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a041",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pa,self.pb,self.sa,self.sb,self.da,self.db,self.priority,self.gate,self.trace,self.latch=(0,7,0,0,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pa,self.pb,self.sa,self.sb,self.da,self.db,self.priority,self.gate,self.trace,self.latch=advance((self.pa,self.pb,self.sa,self.sb,self.da,self.db,self.priority,self.gate,self.trace,self.latch),a)
  elif a==6:
   if (self.pa,self.pb,self.sa,self.sb,self.da,self.db,self.priority,self.gate,self.trace,self.latch)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
