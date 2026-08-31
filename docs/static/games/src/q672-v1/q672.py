"""q672 Semaphore Analogy -- transfer relay relations after contrasting miniature policy tests."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,SOURCE,TARGET,FLAG,BEAM,TEST,GOAL,BAD=5,10,6,12,14,9,11,13,15
LEVELS=[{"name":"Relation Map","seq":(4,)},{"name":"Rotated Signal","seq":(1,4)},{"name":"Relay Gap","seq":(2,1,4)},{"name":"Miniature Tests","seq":(3,1,2,4)},{"name":"Policy Transfer","seq":(1,3,2,1,4)},{"name":"Semaphore Analogy","seq":(2,1,3,2,1,3,4)}]
def advance(s,a):
 source,target,beam,tests,mapped,locked=s;x,y=source;u,v=target
 if a==1:x=(x+1+beam)%5;u=(u+2)%5
 elif a==2:y=(y+2+len(tests))%6;v=(v+1+beam)%6;beam=(beam+1)%3
 elif a==3:tests=tests+((x+y+u+v+beam)%3,)
 elif a==4:mapped=((y-x)%6,(v-u)%6,beam,tests[-2:])
 elif a==5:locked=(mapped,source,target,beam,tests[-2:])
 return (x,y),(u,v),beam,tests,mapped,locked
for x in LEVELS:
 s=((0,2),(1,3),0,(),None,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD;f[8:33,7:29]=SOURCE;f[8:33,35:57]=TARGET
  for side,pair in enumerate((g.source,g.target)):
   ox=10+side*28
   for i,v in enumerate(pair):f[13+i*11:20+i*11,ox:ox+15]=BEAM if side==0 else FLAG;f[15+i*11:18+i*11,ox+2:ox+4+v*2]=FLAG
  for i,v in enumerate(g.tests[-3:]):f[39:44,8+i*15:18+i*15]=TEST;f[45:47,8+i*15:10+i*15+v*2]=BEAM
  f[51:55,8:8+g.beam*15+10]=BEAM
  if g.mapped:f[56:60,8:45]=TARGET
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q672(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q672",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=(0,2);self.target=(1,3);self.beam=0;self.tests=();self.mapped=self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.source,self.target,self.beam,self.tests,self.mapped,self.locked=advance((self.source,self.target,self.beam,self.tests,self.mapped,self.locked),a)
  elif a==6:
   if (self.source,self.target,self.beam,self.tests,self.mapped,self.locked)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
