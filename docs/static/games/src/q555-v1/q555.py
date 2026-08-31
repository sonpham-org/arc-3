"""q555 Vivarium Lesson -- infer a reciprocal partner policy from fair and unfair demonstrations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,STRATUM,FAUNA,DEMO,CONTEXT,FAIR,UNFAIR,GOAL,BAD=1,12,10,14,11,6,9,7,13,15
LEVELS=[
 {"name":"One Offer","shows":1,"switch":0,"gestures":0,"rule":0},
 {"name":"Changed Stratum","shows":1,"switch":1,"gestures":0,"rule":1},
 {"name":"Empty Motion","shows":2,"switch":0,"gestures":1,"rule":1},
 {"name":"Fairness Memory","shows":3,"switch":1,"gestures":1,"rule":0},
 {"name":"Reciprocal Policy","shows":4,"switch":1,"gestures":2,"rule":1},
 {"name":"Vivarium Lesson","shows":5,"switch":1,"gestures":3,"rule":0}]
def advance(s,a,x):
 pos,ctx,seen,fairness,gestures,applied=s
 if a==1:
  offer=(x["rule"]+ctx+len(seen))%2;seen=seen+(offer,);fairness+=1 if offer==ctx else -1;pos=(pos+1+offer)%9
 elif a==2:ctx^=1;pos=(8-pos)%9
 elif a==3:gestures+=1
 elif a in (4,5):
  choice=a-4;partner=int(fairness>=0);correct=(x["rule"]+ctx+partner+sum(seen[-2:]))%2
  if not seen or choice!=correct:return None
  applied=(choice,partner,fairness,pos,gestures)
 return pos,ctx,seen,fairness,gestures,applied
for x in LEVELS:
 base=(1,)*x["shows"]+(2,)*x["switch"]+(3,)*x["gestures"];s=(0,0,(),0,0,None)
 for a in base:s=advance(s,a,x);assert s is not None
 partner=int(s[3]>=0);choice=(x["rule"]+s[1]+partner+sum(s[2][-2:]))%2;x["plan"]=base+(4+choice,)
def target(x):
 s=(0,0,(),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(3):f[8+i*9:15+i*9,8:56]=STRATUM
  for i in range(9):x=10+i*5;f[29:35,x:x+3]=FAUNA if i==g.pos else DEMO
  f[39:43,8:28]=CONTEXT;f[39:43,36:56]=FAIR if g.fairness>=0 else UNFAIR
  for i,v in enumerate(g.seen[-5:]):f[48:53,8+i*9:14+i*9]=FAIR if v else UNFAIR
  if g.applied:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q555(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q555",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=self.ctx=self.fairness=self.gestures=0;self.seen=();self.applied=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.pos,self.ctx,self.seen,self.fairness,self.gestures,self.applied),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.pos,self.ctx,self.seen,self.fairness,self.gestures,self.applied=s
  elif a==6:
   if (self.pos,self.ctx,self.seen,self.fairness,self.gestures,self.applied)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
