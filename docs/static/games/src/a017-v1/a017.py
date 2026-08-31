"""a017 Bent Compass -- learn a reflected rotation from action-outcome calibration."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,PAD,HAZARD,TRAVELER,ARROW,TRACE,GOAL,BAD=6,10,8,12,14,11,5,13,15
LEVELS=[{"name":"First Displacement","seq":(1,3)},{"name":"Second Arrow","seq":(2,3)},{"name":"Reflected Pair","seq":(1,2,3)},{"name":"Leave Pad","seq":(4,2,1,3)},{"name":"Mapped Crossing","seq":(2,3,1,4,2,1,3)},{"name":"Bent Compass","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pos,rotation,reflected,trials,terrain,route=s;x,y=pos
 if a in (1,2):
  dx,dy=((1,0) if a==1 else (0,1));dx,dy=((dy,dx) if reflected else (dx,dy))
  for _ in range(rotation):dx,dy=-dy,dx
  x=(x+dx)%7;y=(y+dy)%7
 elif a==3:trials=trials+((pos,(x,y),rotation,reflected),);terrain=max(0,terrain-1)
 elif a==4:rotation=(rotation+1)%4;reflected=not reflected;terrain=max(0,terrain-1)
 elif a==5:route=((x,y),rotation,reflected,trials[-4:],terrain)
 return (x,y),rotation,reflected,trials,terrain,route
for x in LEVELS:
 s=((3,3),1,True,(),5,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for y in range(7):
   for x in range(7):f[7+y*7:13+y*7,7+x*7:13+x*7]=PAD if 2<=x<=4 and 2<=y<=4 else HAZARD if (x+y)%3==0 else FIELD
  x,y=g.pos;f[7+y*7:13+y*7,7+x*7:13+x*7]=TRAVELER
  for i,_ in enumerate(g.trials[-4:]):f[55:59,8+i*11:17+i*11]=TRACE
  f[1:4,8:8+g.rotation*10+7]=ARROW
  if g.route:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A017(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a017",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=(3,3);self.rotation=1;self.reflected=True;self.trials=();self.terrain=5;self.route=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.rotation,self.reflected,self.trials,self.terrain,self.route=advance((self.pos,self.rotation,self.reflected,self.trials,self.terrain,self.route),a)
  elif a==6:
   if (self.pos,self.rotation,self.reflected,self.trials,self.terrain,self.route)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
