"""a020 Mixed Axes -- factor horizontal and vertical remapping across colored regions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,REGION_A,REGION_B,BALL,ARROW,BOUNDARY,GOAL,BAD=9,10,6,12,14,11,5,13,15
LEVELS=[{"name":"Horizontal Map","seq":(1,3)},{"name":"Vertical Map","seq":(2,3)},{"name":"Axis Factor","seq":(1,2,3)},{"name":"Region Boundary","seq":(4,2,1,3)},{"name":"Rolling Transfer","seq":(2,3,1,4,2,1,3)},{"name":"Mixed Axes","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pos,region,maps,velocity,traces,delivered=s;x,y=pos;vx,vy=velocity;hx,hy=maps[region]
 if a==1:vx=hx;x=(x+vx)%8
 elif a==2:vy=hy;y=(y+vy)%8
 elif a==3:traces=traces+(((x,y),region,(vx,vy),maps[region]),);x=(x+vx)%8;y=(y+vy)%8
 elif a==4:region^=1;hx,hy=maps[region];vx=hx if vx else 0;vy=hy if vy else 0
 elif a==5:delivered=((x,y),region,maps,(vx,vy),traces[-4:])
 return (x,y),region,maps,(vx,vy),traces,delivered
for x in LEVELS:
 s=((1,1),0,((1,-1),(-1,1)),(0,0),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:31]=REGION_A;f[4:60,33:60]=REGION_B;f[4:60,31:33]=BOUNDARY
  for y in range(8):
   for x in range(8):f[6+y*6:11+y*6,6+x*6:11+x*6]=FIELD if (x<4)==(y%2==0) else REGION_A if x<4 else REGION_B
  x,y=g.pos;f[6+y*6:11+y*6,6+x*6:11+x*6]=BALL
  for i,_ in enumerate(g.traces[-4:]):f[55:59,8+i*11:17+i*11]=ARROW
  if g.delivered:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A020(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a020",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=(1,1);self.region=0;self.maps=((1,-1),(-1,1));self.velocity=(0,0);self.traces=();self.delivered=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.region,self.maps,self.velocity,self.traces,self.delivered=advance((self.pos,self.region,self.maps,self.velocity,self.traces,self.delivered),a)
  elif a==6:
   if (self.pos,self.region,self.maps,self.velocity,self.traces,self.delivered)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
