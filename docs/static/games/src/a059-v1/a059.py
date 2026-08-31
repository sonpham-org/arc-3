"""a059 Cruise Beetle -- regulate speed against persistent terrain slope."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SKY,HILL,BEETLE,TRAIL,TARGET,THROTTLE,BRAKE,SLOPE,BAD=3,8,9,12,14,13,10,11,6,15
LEVELS=[
 {"name":"Throttle Pulse","seq":(1,)},{"name":"Brake Pulse","seq":(1,2)},
 {"name":"Read Trail","seq":(1,3,2)},{"name":"Slope Change","seq":(1,4,2,3)},
 {"name":"Cruise Band","seq":(1,1,4,2,3,2,1)},{"name":"Cruise Beetle","seq":(1,4,2,3,1,4,2,2,3,1)},
]
def advance(s,a):
 pos,speed,slope,control,stable,trail,history,snapshot=s
 if a==1:control=min(1,control+1)
 elif a==2:control=max(-1,control-1)
 elif a==3:control=0
 elif a==4:slope=-1 if slope==1 else slope+1
 if a in (1,2,3,4):
  speed=max(0,min(5,speed+control+slope));pos=(pos+speed)%12;stable=min(5,stable+1) if 2<=speed<=3 else 0;trail=(trail+(speed,))[-8:];history=(history+(a,))[-8:]
 elif a==5:snapshot=(pos,speed,slope,control,stable,trail,history)
 return pos,speed,slope,control,stable,trail,history,snapshot
for x in LEVELS:
 s=(0,2,0,0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SKY
  for x in range(5,59):
   y=43+(x//8%3-1)*g.slope;f[y:58,x:x+1]=HILL
  x=7+g.pos*4;f[35:45,x:x+8]=BEETLE
  for i,v in enumerate(g.trail[-8:]):f[47+i%2*4:50+i%2*4,7+i*6:10+i*6]=TRAIL if v>=2 else SLOPE
  f[9:13,8:8+g.speed*8]=TARGET if 2<=g.speed<=3 else TRAIL
  f[16:21,8:20]=THROTTLE if g.control>0 else BRAKE if g.control<0 else SLOPE
  for i in range(g.stable):f[54:57,35+i*4:38+i*4]=TARGET
  if g.bad:f[1:4,18:46]=BAD
  return f
class A059(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a059",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos,self.speed,self.slope,self.control,self.stable,self.trail,self.history,self.snapshot=(0,2,0,0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.speed,self.slope,self.control,self.stable,self.trail,self.history,self.snapshot=advance((self.pos,self.speed,self.slope,self.control,self.stable,self.trail,self.history,self.snapshot),a)
  elif a==6:
   if (self.pos,self.speed,self.slope,self.control,self.stable,self.trail,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
