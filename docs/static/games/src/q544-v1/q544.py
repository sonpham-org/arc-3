"""q544 Moraine Lesson -- infer a conditional local policy that writes an outer token."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,DEMO,RAFT,CONTEXT,GESTURE,POLICY,OUTER,GOAL,BAD=1,9,10,14,6,12,11,7,13,15
LEVELS=[
 {"name":"One Guide","shows":1,"switch":0,"gestures":0,"rule":0},
 {"name":"Changed Crevasse","shows":1,"switch":1,"gestures":0,"rule":1},
 {"name":"Empty Signal","shows":2,"switch":0,"gestures":1,"rule":1},
 {"name":"Outer Lesson","shows":3,"switch":1,"gestures":1,"rule":0},
 {"name":"Nested Policy","shows":4,"switch":1,"gestures":2,"rule":1},
 {"name":"Moraine Lesson","shows":5,"switch":1,"gestures":3,"rule":0}]
def advance(s,a,x):
 pos,ctx,seen,gestures,outer,applied=s;outer=list(outer)
 if a==1:signal=(x["rule"]+ctx+len(seen))%2;seen=seen+(signal,);pos=(pos+1+signal)%8
 elif a==2:ctx^=1;pos=(7-pos)%8
 elif a==3:gestures+=1
 elif a in (4,5):
  choice=a-4;correct=(x["rule"]+ctx+sum(seen[-2:]))%2
  if not seen or choice!=correct:return None
  outer[ctx]=(sum(seen)+choice+gestures)%4;applied=(choice,ctx,tuple(outer))
 return pos,ctx,seen,gestures,tuple(outer),applied
for x in LEVELS:
 base=(1,)*x["shows"]+(2,)*x["switch"]+(3,)*x["gestures"];s=(0,0,(),0,(0,0),None)
 for a in base:s=advance(s,a,x);assert s is not None
 choice=(x["rule"]+s[1]+sum(s[2][-2:]))%2;x["plan"]=base+(4+choice,)
def target(x):
 s=(0,0,(),0,(0,0),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ICE;f[8:30,8:56]=DEMO
  for i in range(8):x=10+i*6;h=4+(i+g.ctx)%3*4;f[27-h:27,x:x+3]=RAFT if i==g.pos else POLICY
  f[35:40,8:28]=CONTEXT;f[35:40,36:56]=GESTURE
  for i,v in enumerate(g.seen[-5:]):f[45:50,8+i*9:14+i*9]=POLICY if v else CONTEXT
  for i,v in enumerate(g.outer):f[53:57,8+i*22:8+i*22+v*4+5]=OUTER
  if g.applied:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q544(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q544",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=self.ctx=self.gestures=0;self.seen=();self.outer=(0,0);self.applied=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.pos,self.ctx,self.seen,self.gestures,self.outer,self.applied),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.pos,self.ctx,self.seen,self.gestures,self.outer,self.applied=s
  elif a==6:
   if (self.pos,self.ctx,self.seen,self.gestures,self.outer,self.applied)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
