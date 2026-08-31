"""q546 Backstage Lesson -- infer a conditional signed policy from thresholded demonstrations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,DEMO,ACTOR,CONTEXT,POSITIVE,NEGATIVE,SOLVED,BAD=1,13,10,14,6,11,9,12,15
LEVELS=[
 {"name":"First Direction","shows":1,"ctx":0,"gesture":0,"threshold":3},{"name":"Context Direction","shows":1,"ctx":1,"gesture":0,"threshold":1},
 {"name":"Empty Gesture","shows":2,"ctx":0,"gesture":1,"threshold":3},{"name":"Threshold Lesson","shows":3,"ctx":1,"gesture":1,"threshold":2},
 {"name":"Signed Policy","shows":4,"ctx":0,"gesture":2,"threshold":5},{"name":"Backstage Lesson","shows":5,"ctx":1,"gesture":2,"threshold":4}]
def advance(s,a,x):
 value,ctx,seen,gesture,solved=s
 if a==1:value+=2 if ctx==0 else -2;seen=seen+(value,)
 elif a==2:ctx^=1
 elif a in (3,4):
  choice=a-3;correct=(ctx+int(value>=x["threshold"]))%2
  if not seen or choice!=correct:return None
  value+=1 if choice else -1;solved=(choice,value)
 elif a==5:gesture+=1
 return value,ctx,seen,gesture,solved
for x in LEVELS:
 base=(1,)*x["shows"]+(2,)*x["ctx"]+(5,)*x["gesture"];s=(0,0,(),0,None)
 for a in base:s=advance(s,a,x);assert s is not None
 x["plan"]=base+(3+((s[1]+int(s[0]>=x["threshold"]))%2),)
def target(x):
 s=(0,0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE;f[8:30,8:56]=DEMO
  center=32;width=min(abs(g.value),12)*2;f[13:25,center:center+width]=POSITIVE if g.value>=0 else NEGATIVE
  f[36:40,8:28]=CONTEXT+g.ctx;f[36:40,36:56]=ACTOR;f[44:48,8:8+g.cfg["threshold"]*5]=POSITIVE
  if g.gesture:f[51:55,8:8+g.gesture*9]=NEGATIVE
  if g.solved:f[54:59,39:56]=SOLVED
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q546(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q546",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.value=self.ctx=self.gesture=0;self.seen=();self.solved=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.value,self.ctx,self.seen,self.gesture,self.solved),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.value,self.ctx,self.seen,self.gesture,self.solved=s
  elif a==6:
   if (self.value,self.ctx,self.seen,self.gesture,self.solved)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
