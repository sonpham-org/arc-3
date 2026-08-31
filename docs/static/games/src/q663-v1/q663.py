"""q663 Murmuration Analogy -- transfer geometric relations to flocks under a parity constraint."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,SOURCE,TARGET,FLOCK,WIND,PARITY,GOAL,BAD=5,11,6,12,14,10,9,13,15
LEVELS=[
 {"name":"Relation Map","seq":(4,)},{"name":"Rotated Surface","seq":(1,4)},
 {"name":"Wind Gap","seq":(2,1,4)},{"name":"Parity Transfer","seq":(3,1,2,4)},
 {"name":"Flock Algebra","seq":(1,3,2,1,4)},
 {"name":"Murmuration Analogy","seq":(2,1,3,2,1,3,4)}]
def advance(s,a):
 source,target,wind,parity,mapped,locked=s;x,y=source;u,v=target
 if a==1:x=(x+1+wind)%5;u=(u+2)%5;parity^=1
 elif a==2:y=(y+2+parity)%6;v=(v+1+wind)%6;wind=(wind+1)%3
 elif a==3:parity^=((x+y+u+v)%2)
 elif a==4:mapped=((y-x)%6,(v-u)%6,wind,parity)
 elif a==5:locked=(mapped,source,target,wind,parity)
 return (x,y),(u,v),wind,parity,mapped,locked
for x in LEVELS:
 s=((0,2),(1,3),0,0,None,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=AVIARY;f[8:33,7:29]=SOURCE;f[8:33,35:57]=TARGET
  for side,pair in enumerate((g.source,g.target)):
   ox=10+side*28
   for i,v in enumerate(pair):f[13+i*11:20+i*11,ox:ox+15]=WIND if side==0 else FLOCK;f[15+i*11:18+i*11,ox+2:ox+4+v*2]=FLOCK
  f[39:44,8:8+g.wind*15+10]=WIND;f[47:51,8:8+g.parity*25+12]=PARITY
  if g.mapped:f[54:58,8:45]=TARGET
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q663(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q663",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=(0,2);self.target=(1,3);self.wind=self.parity=0;self.mapped=self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.source,self.target,self.wind,self.parity,self.mapped,self.locked=advance((self.source,self.target,self.wind,self.parity,self.mapped,self.locked),a)
  elif a==6:
   if (self.source,self.target,self.wind,self.parity,self.mapped,self.locked)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
