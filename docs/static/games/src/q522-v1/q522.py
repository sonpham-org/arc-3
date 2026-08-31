"""q522 Semaphore Frame -- compose flag motion across moving local relay frames."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,FLAG,BEAM,FRAME,TEST,COMMIT,GOAL,BAD=0,8,14,10,6,11,12,13,15
LEVELS=[
 {"name":"Local Flag","seq":(1,)},{"name":"Rotated Beam","seq":(2,1)},
 {"name":"Miniature Test","seq":(1,3,2)},{"name":"Translated Relay","seq":(2,1,4,3)},
 {"name":"Two Testbeds","seq":(1,2,3,4,1,2)},
 {"name":"Semaphore Frame","seq":(2,1,4,3,2,1,3,4,1)}]
def advance(s,a):
 flag,beam,rotation,tests,locked=s
 if a==1:flag=(flag+1+rotation+beam)%8
 elif a==2:rotation=(rotation+1)%4;beam=(beam+rotation)%5
 elif a==3:tests=tests+((flag+beam+rotation)%3,)
 elif a==4:beam=(beam+2+len(tests))%5;flag=(flag+beam)%8
 elif a==5:locked=(flag,beam,rotation,tests[-3:])
 return flag,beam,rotation,tests,locked
for x in LEVELS:
 s=(0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD
  for i in range(5):
   x=8+i*10;f[8:30,x:x+7]=BEAM if i==g.beam else FRAME;f[11+(i%3)*5:16+(i%3)*5,x+2:x+6]=FLAG
  for i in range(8):x=8+i*6;f[34:39,x:x+4]=FLAG if i==g.flag else FRAME
  for i,v in enumerate(g.tests[-4:]):f[44:49,8+i*12:17+i*12]=TEST;f[50:52,8+i*12:10+i*12+v*2]=COMMIT
  f[55:59,8:8+g.rotation*11+7]=FRAME
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q522(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q522",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.flag=self.beam=self.rotation=0;self.tests=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.flag,self.beam,self.rotation,self.tests,self.locked=advance((self.flag,self.beam,self.rotation,self.tests,self.locked),a)
  elif a==6:
   if (self.flag,self.beam,self.rotation,self.tests,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
