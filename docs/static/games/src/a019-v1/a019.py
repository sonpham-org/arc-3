"""a019 Sticky Controls -- learn command persistence and brake before obstacles."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LANE,ROAD,OBSTACLE,RIDER,COMMAND,MEMORY,GOAL,BAD=8,10,6,12,14,11,5,13,15
LEVELS=[{"name":"Held Command","seq":(1,3)},{"name":"Opposite Brake","seq":(2,3)},{"name":"Persistence Test","seq":(1,2,3)},{"name":"Moving Obstacle","seq":(4,2,1,3)},{"name":"Early Braking","seq":(2,3,1,4,2,1,3)},{"name":"Sticky Controls","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pos,velocity,persist,last,trials,obstacle,parked=s
 if a==1:
  if last==2:velocity=0;persist=0
  else:velocity=1;persist=(persist+1)%4
  last=1;pos=(pos+velocity*(1+persist))%12
 elif a==2:
  if last==1:velocity=0;persist=0
  else:velocity=-1;persist=(persist+1)%4
  last=2;pos=(pos+velocity*(1+persist))%12
 elif a==3:trials=trials+((pos,velocity,persist,last,obstacle),)
 elif a==4:obstacle=(obstacle+2)%12;pos=(pos+velocity)%12
 elif a==5:parked=(pos,velocity,persist,last,trials[-4:],obstacle)
 return pos,velocity,persist,last,trials,obstacle,parked
for x in LEVELS:
 s=(0,0,0,0,(),7,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LANE;f[10:32,7:57]=ROAD
  for i in range(12):x=8+i*4;f[18:24,x:x+3]=OBSTACLE if i==g.obstacle else ROAD
  x=8+g.pos*4;f[13:29,x:x+4]=RIDER
  for i,(_,v,p,_,_) in enumerate(g.trials[-4:]):x=8+i*12;f[38:44,x:x+9]=COMMAND;f[45:48,x:x+2+abs(v)*3]=MEMORY;f[49:52,x:x+2+p*2]=OBSTACLE
  if g.parked:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A019(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a019",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=self.velocity=self.persist=self.last=0;self.trials=();self.obstacle=7;self.parked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.velocity,self.persist,self.last,self.trials,self.obstacle,self.parked=advance((self.pos,self.velocity,self.persist,self.last,self.trials,self.obstacle,self.parked),a)
  elif a==6:
   if (self.pos,self.velocity,self.persist,self.last,self.trials,self.obstacle,self.parked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
