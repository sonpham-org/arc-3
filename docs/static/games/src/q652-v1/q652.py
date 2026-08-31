"""q652 Tide Analogy -- transfer reversing-current relations before irreversible commitment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,SOURCE,TARGET,COMMIT,GOAL,BAD=5,10,9,14,6,12,11,13,15
LEVELS=[
 {"name":"Current Pair","seq":(1,)},{"name":"Changed Shells","seq":(2,1)},
 {"name":"Mapped Tide","seq":(1,3,2)},{"name":"Safe Gate","seq":(2,1,3,4)},
 {"name":"Surface Transfer","seq":(1,2,3,1,2,4)},
 {"name":"Tide Analogy","seq":(2,1,3,2,1,3,1,2,4)}]
def advance(s,a):
 source,target,tide,mapped,irreversible,locked=s;x,y=source;u,v=target
 if a==1:tide^=1;x=(x+1+tide)%5;u=(u+2-tide)%5
 elif a==2:y=(y+2+tide)%6;v=(v+1+2*tide)%6
 elif a==3:mapped=((y-x)%6,(v-u)%6,tide)
 elif a==4:irreversible=(mapped,tide,source,target)
 elif a==5:locked=(irreversible,mapped,source,target,tide)
 return (x,y),(u,v),tide,mapped,irreversible,locked
for x in LEVELS:
 s=((0,2),(1,3),0,None,None,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:33,7:29]=SOURCE;f[8:33,35:57]=TARGET
  for side,pair in enumerate((g.source,g.target)):
   ox=10+side*28
   for i,v in enumerate(pair):f[13+i*11:20+i*11,ox:ox+15]=CURRENT if side==0 else SHELL;f[15+i*11:18+i*11,ox+2:ox+4+v*2]=SHELL
  f[39:44,8:8+g.tide*25+12]=CURRENT
  if g.mapped:f[47:51,8:45]=TARGET
  if g.irreversible:f[54:58,8:45]=COMMIT
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q652(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q652",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=(0,2);self.target=(1,3);self.tide=0;self.mapped=self.irreversible=self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.source,self.target,self.tide,self.mapped,self.irreversible,self.locked=advance((self.source,self.target,self.tide,self.mapped,self.irreversible,self.locked),a)
  elif a==6:
   if (self.source,self.target,self.tide,self.mapped,self.irreversible,self.locked)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
