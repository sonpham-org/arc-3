"""a067 Nyquist Bridge -- increase probe rate before trusting a fast load cycle."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,RIVER,BRIDGE,LOAD_A,LOAD_B,LOAD_C,PROBE,CART,INTERVAL,BAD=11,8,9,12,14,10,13,6,4,15
LEVELS=[
 {"name":"Default Probe","seq":(1,)},{"name":"Double Rate","seq":(2,1)},
 {"name":"Resolve Cycle","seq":(2,1,1)},{"name":"Slow Comparison","seq":(3,1,2,1,4)},
 {"name":"Safe Dispatch","seq":(2,1,1,3,1,4,1)},{"name":"Nyquist Bridge","seq":(1,2,1,1,3,1,2,1,4,1)},
]
def advance(s,a):
 phase,interval,observations,cart,risk,clock,history,snapshot=s
 if a==1:phase=(phase+interval*2)%6;clock=(clock+interval)%12;observations=(observations+(phase,))[-6:];history=(history+(1,))[-8:]
 elif a==2:interval=max(1,interval//2);history=(history+(2,))[-8:]
 elif a==3:interval=min(4,interval*2);history=(history+(3,))[-8:]
 elif a==4:cart=(cart+1+int(phase in (0,3)))%7;risk=(risk+int(phase in (1,4)))%5;history=(history+(4,))[-8:]
 elif a==5:snapshot=(phase,interval,observations,cart,risk,clock,history)
 return phase,interval,observations,cart,risk,clock,history,snapshot
for x in LEVELS:
 s=(0,4,(),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=RIVER;f[25:39,6:58]=BRIDGE
  loads=(LOAD_A,LOAD_B,LOAD_C,LOAD_A,LOAD_B,LOAD_C);f[18:25,12+g.phase*7:18+g.phase*7]=loads[g.phase]
  x=8+g.cart*7;f[28:37,x:x+7]=CART
  f[8:12,8:8+g.interval*10]=INTERVAL
  for i,v in enumerate(g.observations):f[47:52,8+i*8:14+i*8]=loads[v]
  for i in range(g.risk):f[54:58,42+i*4:46+i*4]=BAD
  f[14:18,48:56]=PROBE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A067(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a067",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase,self.interval,self.observations,self.cart,self.risk,self.clock,self.history,self.snapshot=(0,4,(),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phase,self.interval,self.observations,self.cart,self.risk,self.clock,self.history,self.snapshot=advance((self.phase,self.interval,self.observations,self.cart,self.risk,self.clock,self.history,self.snapshot),a)
  elif a==6:
   if (self.phase,self.interval,self.observations,self.cart,self.risk,self.clock,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
