"""a022 Gain Garden -- calibrate zone-specific push magnitude before placing fragile seeds."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,SOIL_A,SOIL_B,STONE,SEED,TRACE,GOAL,BAD=1,10,8,12,14,11,6,13,15
LEVELS=[{"name":"One Push","seq":(1,3)},{"name":"Second Zone","seq":(2,3)},{"name":"Gain Contrast","seq":(1,2,3)},{"name":"Move Test Stone","seq":(4,2,1,3)},{"name":"Fragile Placement","seq":(2,3,1,4,2,1,3)},{"name":"Gain Garden","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 stone,zone,gains,seeds,traces,placed=s
 if a==1:stone=(stone+gains[zone])%12
 elif a==2:zone^=1;stone=(stone+gains[zone])%12
 elif a==3:traces=traces+((stone,zone,gains[zone]),)
 elif a==4:seeds=tuple((v+gains[zone])%12 for v in seeds);zone^=1
 elif a==5:placed=(stone,zone,gains,seeds,traces[-4:])
 return stone,zone,gains,seeds,traces,placed
for x in LEVELS:
 s=(0,0,(1,3),(2,7,10),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:32]=SOIL_A;f[4:60,32:60]=SOIL_B
  for i in range(12):x=7+(i%6)*9;y=9+(i//6)*18;f[y:y+12,x:x+7]=GARDEN
  x=7+(g.stone%6)*9;y=9+(g.stone//6)*18;f[y+2:y+10,x+1:x+6]=STONE
  for s in g.seeds:x=7+(s%6)*9;y=9+(s//6)*18;f[y+4:y+9,x+2:x+5]=SEED
  for i,(_,_,v) in enumerate(g.traces[-4:]):x=8+i*12;f[48:53,x:x+9]=TRACE;f[54:57,x:x+2+v*2]=STONE
  if g.placed:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A022(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a022",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stone=0;self.zone=0;self.gains=(1,3);self.seeds=(2,7,10);self.traces=();self.placed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.stone,self.zone,self.gains,self.seeds,self.traces,self.placed=advance((self.stone,self.zone,self.gains,self.seeds,self.traces,self.placed),a)
  elif a==6:
   if (self.stone,self.zone,self.gains,self.seeds,self.traces,self.placed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
