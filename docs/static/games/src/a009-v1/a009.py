"""a009 Patch Cable -- preserve service by attaching a bypass before removing a broken edge."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GRID,NODE,EDGE,POWER,BYPASS,BROKEN,GOAL,BAD=8,10,14,6,11,12,5,13,15
LEVELS=[{"name":"Live Sink","seq":(1,)},{"name":"Second Route","seq":(2,1)},{"name":"Temporary Bypass","seq":(3,1,2)},{"name":"Safe Removal","seq":(4,2,1,3)},{"name":"Service Continuity","seq":(2,3,1,4,2,1)},{"name":"Patch Cable","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 route,power,bypass,removed,history,sealed=s
 if a==1:route=(route+1)%4;power=(power+1+int(bypass))%5;history=history+((1,route,power,bypass,removed),)
 elif a==2:route=(route+2)%4;power=(power+2-int(removed))%5;history=history+((2,route,power,bypass,removed),)
 elif a==3:bypass=True;power=min(4,power+1);history=history+((3,route,power,bypass,removed),)
 elif a==4:removed=True;power=max(0,power-(0 if bypass else 3));history=history+((4,route,power,bypass,removed),)
 elif a==5:sealed=(route,power,bypass,removed,history[-5:])
 return route,power,bypass,removed,history,sealed
for x in LEVELS:
 s=(0,2,False,False,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GRID
  pts=[(10,12),(30,9),(49,15),(18,31),(42,32),(12,49),(51,49)]
  for x,y in pts:f[y:y+7,x:x+7]=NODE
  f[15:18,16:49]=EDGE;f[34:37,20:45]=BROKEN if not g.removed else GRID;f[20:48,13:16]=EDGE;f[20:48,52:55]=EDGE
  if g.bypass:f[27:31,19:48]=BYPASS
  f[52:56,8:8+g.power*10]=POWER
  if g.sealed:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A009(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a009",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.route=0;self.power=2;self.bypass=self.removed=False;self.history=();self.sealed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.route,self.power,self.bypass,self.removed,self.history,self.sealed=advance((self.route,self.power,self.bypass,self.removed,self.history,self.sealed),a)
  elif a==6:
   if (self.route,self.power,self.bypass,self.removed,self.history,self.sealed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
