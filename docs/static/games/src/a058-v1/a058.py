"""a058 Reservoir Governor -- distribute intermittent pump volume safely."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,TANK,WATER,VALVE,PUMP,SAFE,FLOW,ALARM,BAD=2,8,9,12,14,10,13,6,4,15
LEVELS=[
 {"name":"Open Valve","seq":(1,)},{"name":"Pump Pulse","seq":(1,3)},
 {"name":"Coupled Levels","seq":(1,2,3)},{"name":"Redistribute","seq":(1,3,2,3,4)},
 {"name":"Intermittent Pump","seq":(4,1,3,2,3,1,3)},{"name":"Reservoir Governor","seq":(1,3,2,4,3,1,2,3,4,3)},
]
def advance(s,a):
 levels,valves,pump,safe,overflow,history,snapshot=s;lv=list(levels);v=list(valves)
 if a==1:v[0]^=1;history=(history+(1,))[-8:]
 elif a==2:v[1]^=1;history=(history+(2,))[-8:]
 elif a==3:
  if pump in (0,2):lv[0]+=1
  if v[0] and lv[0]>lv[1]:lv[0]-=1;lv[1]+=1
  if v[1] and lv[1]>lv[2]:lv[1]-=1;lv[2]+=1
  overflow=(overflow+sum(int(x>6) for x in lv))%6;lv=[min(7,x) for x in lv];safe=min(5,safe+1) if all(2<=x<=5 for x in lv) else 0;pump=(pump+1)%4;history=(history+(3,))[-8:]
 elif a==4:pump=(pump+2)%4;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(lv),tuple(v),pump,safe,overflow,history)
 return tuple(lv),tuple(v),pump,safe,overflow,history,snapshot
for x in LEVELS:
 s=((3,2,4),(0,0),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i,v in enumerate(g.levels):
   x=8+i*18;f[15:48,x:x+13]=TANK;f[46-v*4:47,x+2:x+11]=WATER;f[27:31,x+1:x+12]=SAFE
  f[30:35,21:27]=VALVE if g.valves[0] else FLOW;f[30:35,39:45]=VALVE if g.valves[1] else FLOW
  f[8:13,8:22]=PUMP;f[8:13,24:24+g.pump*6]=FLOW
  for i in range(g.safe):f[53:57,8+i*8:14+i*8]=SAFE
  for i in range(g.overflow):f[53:57,50+i*2:52+i*2]=ALARM
  if g.bad:f[1:4,18:46]=BAD
  return f
class A058(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a058",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.levels,self.valves,self.pump,self.safe,self.overflow,self.history,self.snapshot=((3,2,4),(0,0),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.levels,self.valves,self.pump,self.safe,self.overflow,self.history,self.snapshot=advance((self.levels,self.valves,self.pump,self.safe,self.overflow,self.history,self.snapshot),a)
  elif a==6:
   if (self.levels,self.valves,self.pump,self.safe,self.overflow,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
