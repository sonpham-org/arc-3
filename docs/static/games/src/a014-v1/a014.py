"""a014 Sealant Trail -- repair every crack without sealing the drone away from the exit."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,FLOOR,DRONE,CRACK,WET,CURED,GOAL,BAD=3,10,8,14,11,6,12,13,15
LEVELS=[{"name":"First Crack","seq":(1,3)},{"name":"Turn Around","seq":(2,3)},{"name":"Wet Barrier","seq":(1,2,3)},{"name":"Curing Pulse","seq":(4,2,1,3)},{"name":"Exit Corridor","seq":(2,3,1,4,2,1,3)},{"name":"Sealant Trail","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pos,direction,cracks,wet,cured,pressure,route=s;w=list(wet);c=set(cured)
 if a==1:pos=(pos+direction)%12
 elif a==2:direction*=-1;pos=(pos+direction*2)%12
 elif a==3:
  crack=cracks[pos%len(cracks)]
  if pos%6==crack:c.add(crack);w.append(pos)
  pressure=min(5,pressure+int(crack in c))
 elif a==4:w=w[1:];pressure=(pressure+len(c))%6;direction*=-1
 elif a==5:route=(pos,direction,tuple(w),tuple(sorted(c)),pressure)
 return pos,direction,cracks,tuple(w),tuple(sorted(c)),pressure,route
for x in LEVELS:
 s=(0,1,(1,3,5),(),(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i in range(12):x=8+(i%6)*8;y=9+(i//6)*14;f[y:y+9,x:x+7]=FLOOR;f[y+3:y+6,x+2:x+5]=CURED if i%6 in g.cured else CRACK if i%6 in g.cracks else FLOOR
  x=8+(g.pos%6)*8;y=9+(g.pos//6)*14;f[y+1:y+8,x+1:x+6]=DRONE
  for p in g.wet:x=8+(p%6)*8;y=9+(p//6)*14;f[y+7:y+9,x:x+7]=WET
  f[45:49,8:8+g.pressure*9]=CURED
  if g.route:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A014(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a014",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=0;self.direction=1;self.cracks=(1,3,5);self.wet=self.cured=();self.pressure=0;self.route=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.direction,self.cracks,self.wet,self.cured,self.pressure,self.route=advance((self.pos,self.direction,self.cracks,self.wet,self.cured,self.pressure,self.route),a)
  elif a==6:
   if (self.pos,self.direction,self.cracks,self.wet,self.cured,self.pressure,self.route)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
