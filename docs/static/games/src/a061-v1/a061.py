"""a061 Predator Valve -- regulate a coupled two-species habitat."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HABITAT,PATCH,PREY,PREDATOR,VALVE,BAND,MIGRATE,RESTORE,BAD=5,8,9,12,14,10,13,6,11,15
LEVELS=[
 {"name":"Open Migration","seq":(1,)},{"name":"Ecology Tick","seq":(1,3)},
 {"name":"Second Valve","seq":(2,3)},{"name":"Coupled Oscillation","seq":(1,3,2,3,4)},
 {"name":"Safe Population","seq":(1,3,2,3,3,4,1)},{"name":"Predator Valve","seq":(1,3,2,4,3,1,3,2,3,4)},
]
def advance(s,a):
 prey,pred,valves,season,stable,history,snapshot=s;py=list(prey);pd=list(pred);v=list(valves)
 if a==1:v[0]^=1;history=(history+(1,))[-8:]
 elif a==2:v[1]^=1;history=(history+(2,))[-8:]
 elif a==3:
  for i in range(2):py[i]=max(0,min(7,py[i]+1+season-pd[i]//3));pd[i]=max(0,min(7,pd[i]+py[i]//4-1))
  if v[0] and py[0]>py[1]:py[0]-=1;py[1]+=1
  if v[1] and pd[1]>pd[0]:pd[1]-=1;pd[0]+=1
  stable=min(5,stable+1) if all(2<=x<=5 for x in py+pd) else 0;season^=1;history=(history+(3,))[-8:]
 elif a==4:season^=1;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(py),tuple(pd),tuple(v),season,stable,history)
 return tuple(py),tuple(pd),tuple(v),season,stable,history,snapshot
for x in LEVELS:
 s=((4,2),(2,4),(0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HABITAT
  for i in range(2):
   x=7+i*29;f[13:49,x:x+22]=PATCH;f[29:33,x:x+22]=BAND
   for j in range(g.prey[i]):f[16+(j//4)*6:20+(j//4)*6,x+3+(j%4)*5:x+7+(j%4)*5]=PREY
   for j in range(g.pred[i]):f[36+(j//4)*6:40+(j//4)*6,x+3+(j%4)*5:x+7+(j%4)*5]=PREDATOR
  f[20:27,30:35]=VALVE if g.valves[0] else MIGRATE;f[38:45,30:35]=VALVE if g.valves[1] else MIGRATE
  for i in range(g.stable):f[54:58,9+i*9:16+i*9]=RESTORE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A061(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a061",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.prey,self.pred,self.valves,self.season,self.stable,self.history,self.snapshot=((4,2),(2,4),(0,0),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.prey,self.pred,self.valves,self.season,self.stable,self.history,self.snapshot=advance((self.prey,self.pred,self.valves,self.season,self.stable,self.history,self.snapshot),a)
  elif a==6:
   if (self.prey,self.pred,self.valves,self.season,self.stable,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
