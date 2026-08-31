"""q120 Hidden Policy Handoff -- continue a tutor policy from its latent transfer state."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,TUTOR,TOKEN,LATENT,HANDOFF,PLAYER,GOAL,BAD=0,10,9,14,6,11,4,7,15
def expected(p,s):return((p*s+p)%3)+1
def make(p,d,n):
 s=0;a=[]
 for _ in range(d):x=expected(p,s);a.append(4);s=(s+x+p)%5
 a.append(5)
 for _ in range(n):x=expected(p,s);a.append(x);s=(s+x+p)%5
 return tuple(a)
LEVELS=[{"name":"One-Step Handoff","policy":1,"demo":1,"play":1,"plan":make(1,1,1)},{"name":"Hidden State","policy":2,"demo":2,"play":1,"plan":make(2,2,1)},{"name":"Longer Continuation","policy":3,"demo":2,"play":2,"plan":make(3,2,2)},{"name":"Mid-Pattern Transfer","policy":1,"demo":3,"play":3,"plan":make(1,3,3)},{"name":"Latent Cycle","policy":2,"demo":4,"play":4,"plan":make(2,4,4)},{"name":"Hidden Policy Handoff","policy":3,"demo":5,"play":5,"plan":make(3,5,5)}]
def advance(s,a,x):
 latent,tutor,player,transferred,trace=s;trace=list(trace)
 if a==4 and not transferred:y=expected(x["policy"],latent);trace.append((0,y,latent));latent=(latent+y+x["policy"])%5;tutor+=1
 elif a==5 and not transferred:transferred=True;trace.append((2,latent))
 elif a in (1,2,3) and transferred:
  if a!=expected(x["policy"],latent):return None
  trace.append((1,a,latent));latent=(latent+a+x["policy"])%5;player+=1
 else:return None
 return latent,tutor,player,transferred,tuple(trace)
def target(x):
 s=(0,0,0,False,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE;f[8:31,7:29]=TUTOR;f[8:31,35:57]=PLAYER
  for i,e in enumerate(g.trace[-8:]):x=9+(i%4)*10;y=11+(i//4)*10;f[y:y+6,x:x+7]=TOKEN-(e[0]%3)
  f[37:40,8:11+g.latent*9]=LATENT;f[46:49,8:24]=HANDOFF if g.transferred else TUTOR;f[54:57,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q120(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q120",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.latent=self.tutor=self.player=0;self.transferred=False;self.trace=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.latent,self.tutor,self.player,self.transferred,self.trace),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.latent,self.tutor,self.player,self.transferred,self.trace=s
  elif a==6:
   if (self.latent,self.tutor,self.player,self.transferred,self.trace)==self.target and self.player==x["play"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
