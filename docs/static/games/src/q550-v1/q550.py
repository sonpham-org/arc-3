"""q550 Vault Lesson -- infer a conditional policy while two echo totals stay conserved."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,DEMO,A_ECHO,B_ECHO,CONTEXT,GESTURE,SOLVED,BAD=1,11,9,14,10,12,6,13,15
LEVELS=[
 {"name":"First Demonstration","shows":1,"ctx":0,"gesture":0},{"name":"Context Echo","shows":1,"ctx":1,"gesture":0},
 {"name":"Empty Knock","shows":2,"ctx":0,"gesture":1},{"name":"Paired Lesson","shows":3,"ctx":1,"gesture":1},
 {"name":"Long Demonstration","shows":4,"ctx":0,"gesture":2},{"name":"Vault Lesson","shows":5,"ctx":1,"gesture":2}]
def advance(s,a,x):
 boxes,ctx,seen,gesture,solved=s;b=[list(v) for v in boxes]
 if a==1:
  if ctx==0:b[0][0],b[1][0]=b[1][0],b[0][0]
  else:b[1][1],b[2][1]=b[2][1],b[1][1]
  seen=seen+((ctx,tuple(map(tuple,b))),)
 elif a==2:ctx^=1
 elif a in (3,4):
  choice=a-3;correct=(ctx+sum(b[1]))%2
  if not seen or choice!=correct:return None
  q=choice;b[0][q],b[2][q]=b[2][q],b[0][q];solved=(choice,tuple(map(tuple,b)))
 elif a==5:gesture+=1
 return tuple(map(tuple,b)),ctx,seen,gesture,solved
for x in LEVELS:
 base=(1,)*x["shows"]+(2,)*x["ctx"]+(5,)*x["gesture"];s=(((2,1),(0,1),(1,0)),0,(),0,None)
 for a in base:s=advance(s,a,x);assert s is not None
 x["plan"]=base+(3+((s[1]+sum(s[0][1]))%2),)
def target(x):
 s=(((2,1),(0,1),(1,0)),0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT;f[8:30,8:56]=DEMO
  for i,(a,b) in enumerate(g.boxes):
   x=10+i*15;f[13:19,x:x+a*4]=A_ECHO;f[21:27,x:x+b*4]=B_ECHO
  f[36:40,8:28]=CONTEXT+g.ctx;f[36:40,36:56]=A_ECHO;f[44:48,36:56]=B_ECHO
  if g.gesture:f[51:55,8:8+g.gesture*9]=GESTURE
  if g.solved:f[54:59,39:56]=SOLVED
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q550(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q550",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.boxes=((2,1),(0,1),(1,0));self.ctx=self.gesture=0;self.seen=();self.solved=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.boxes,self.ctx,self.seen,self.gesture,self.solved),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.boxes,self.ctx,self.seen,self.gesture,self.solved=s
  elif a==6:
   if (self.boxes,self.ctx,self.seen,self.gesture,self.solved)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
