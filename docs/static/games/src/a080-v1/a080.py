"""a080 Tendon Hand -- coordinate underactuated fingers around fragile objects."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TABLE,PALM,FINGER,TENDON_A,TENDON_B,TENDON_C,OBJECT,FRAGILE,BAD=8,9,4,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Pull First Tendon","seq":(1,)},{"name":"Pull Second Tendon","seq":(2,)},
 {"name":"Shared Joints","seq":(1,2,3)},{"name":"Shape The Grip","seq":(1,3,2,3,4)},
 {"name":"Fragile Contact","seq":(1,2,3,1,4,3,2)},{"name":"Tendon Hand","seq":(1,3,2,3,1,4,2,3,4,1)},
]
COUPLING=((1,1,0,0,1,0),(0,1,1,1,0,0),(1,0,0,1,1,1))
def joints_for(tensions):return tuple(min(4,sum(tensions[k]*COUPLING[k][j] for k in range(3))) for j in range(6))
def advance(s,a):
 tensions,joints,cursor,obj,pressure,grasped,history,snapshot=s;t=list(tensions)
 if a==1:t[cursor]=min(3,t[cursor]+1);history=(history+(1,))[-8:]
 elif a==2:t[cursor]=max(0,t[cursor]-1);history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;history=(history+(3,))[-8:]
 if a in (1,2,3):joints=joints_for(tuple(t));pressure=sum(joints[i] for i in (1,3,5))%8
 elif a==4:grasped=(tuple(t),joints,obj,pressure);obj=(obj+1)%3;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(t),joints,cursor,obj,pressure,grasped,history)
 return tuple(t),joints,cursor,obj,pressure,grasped,history,snapshot
for x in LEVELS:
 s=((0,0,0),joints_for((0,0,0)),0,0,0,None,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TABLE;f[35:55,21:44]=PALM
  cols=(TENDON_A,TENDON_B,TENDON_C)
  for finger in range(3):
   x=12+finger*18;curl=g.joints[finger*2]+g.joints[finger*2+1];f[12+curl:38,x:x+9]=FINGER;f[9:13,x:x+9]=cols[finger]
   f[54-g.tensions[finger]*4:56,x+2:x+7]=cols[finger]
  f[22:35,27:39]=(OBJECT,FRAGILE,TENDON_C)[g.obj]
  f[7:11,8+g.cursor*17:20+g.cursor*17]=cols[g.cursor]
  for i in range(g.pressure):f[56:59,8+i*6:13+i*6]=FRAGILE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A080(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a080",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tensions,self.joints,self.cursor,self.obj,self.pressure,self.grasped,self.history,self.snapshot=((0,0,0),joints_for((0,0,0)),0,0,0,None,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tensions,self.joints,self.cursor,self.obj,self.pressure,self.grasped,self.history,self.snapshot=advance((self.tensions,self.joints,self.cursor,self.obj,self.pressure,self.grasped,self.history,self.snapshot),a)
  elif a==6:
   if (self.tensions,self.joints,self.cursor,self.obj,self.pressure,self.grasped,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
