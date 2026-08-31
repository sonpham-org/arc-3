"""a016 Graceful Degradation -- preserve steering and braking as optional modules fail."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROAD,VEHICLE,MODULE,POWER,FAILURE,CORE,GOAL,BAD=5,10,14,8,11,12,6,13,15
LEVELS=[{"name":"First Failure","seq":(1,)},{"name":"Power Reroute","seq":(2,1)},{"name":"Drop Optional","seq":(3,1,2)},{"name":"Damage Step","seq":(4,2,1,3)},{"name":"Minimum Vehicle","seq":(2,3,1,4,2,1)},{"name":"Graceful Degradation","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 modules,power,damage,distance,history,docked=s;m=list(modules);p=list(power)
 if a==1:p[(damage+1)%5]=(p[(damage+1)%5]+1)%3;distance+=int(m[0] and m[1])
 elif a==2:p=p[1:]+p[:1];distance+=int(sum(p[:2])>=1)
 elif a==3:i=2+(damage%3);m[i]=False;p[i]=0;distance+=int(m[0] and m[1])
 elif a==4:m[damage%5]=False;damage=(damage+2)%5;history=history+((tuple(m),tuple(p),damage,distance),)
 elif a==5:docked=(tuple(m),tuple(p),damage,distance,history[-4:])
 return tuple(m),tuple(p),damage,distance,history,docked
for x in LEVELS:
 s=((True,True,True,True,True),(1,1,1,1,1),2,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ROAD;f[10:32,8:56]=VEHICLE
  for i,(on,p) in enumerate(zip(g.modules,g.power)):x=9+i*9;f[16:27,x:x+7]=CORE if i<2 and on else MODULE if on else FAILURE;f[28:31,x:x+2+p*2]=POWER
  for i,_ in enumerate(g.history[-4:]):f[38:44,8+i*12:17+i*12]=FAILURE
  f[49:54,8:8+min(6,g.distance)*8]=POWER
  if g.docked:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A016(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a016",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.modules=(True,True,True,True,True);self.power=(1,1,1,1,1);self.damage=2;self.distance=0;self.history=();self.docked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.modules,self.power,self.damage,self.distance,self.history,self.docked=advance((self.modules,self.power,self.damage,self.distance,self.history,self.docked),a)
  elif a==6:
   if (self.modules,self.power,self.damage,self.distance,self.history,self.docked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
