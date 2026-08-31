"""q548 Asterism Lesson -- infer a conditional star policy from demonstrations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,STAR,DEMO,CONTEXT,GESTURE,POLICY,GOAL,BAD=1,12,11,10,6,14,9,13,15
LEVELS=[
 {"name":"One Example","shows":1,"switch":0,"gestures":0,"rule":0},
 {"name":"Changed Sky","shows":1,"switch":1,"gestures":0,"rule":1},
 {"name":"Empty Gesture","shows":2,"switch":0,"gestures":1,"rule":1},
 {"name":"Conditional Lesson","shows":3,"switch":1,"gestures":1,"rule":0},
 {"name":"Precessed Policy","shows":4,"switch":1,"gestures":2,"rule":1},
 {"name":"Asterism Lesson","shows":5,"switch":1,"gestures":3,"rule":0}]
def advance(s,a,x):
 pos,ctx,seen,gestures,applied=s
 if a==1:
  signal=(len(seen)+ctx+x["rule"])%2;seen=seen+(signal,);pos=(pos+1+signal)%8
 elif a==2:ctx^=1;pos=(pos+2)%8
 elif a==3:gestures+=1
 elif a in (4,5):
  choice=a-4;correct=(x["rule"]+ctx+(sum(seen)%2))%2
  if not seen or choice!=correct:return None
  applied=(choice,pos,ctx,len(seen),gestures)
 return pos,ctx,seen,gestures,applied
for x in LEVELS:
 base=(1,)*x["shows"]+(2,)*x["switch"]+(3,)*x["gestures"];s=(0,0,(),0,None)
 for a in base:s=advance(s,a,x);assert s is not None
 choice=(x["rule"]+s[1]+sum(s[2])%2)%2;x["plan"]=base+(4+choice,)
def target(x):
 s=(0,0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;f[8:29,8:56]=DEMO
  for i in range(8):
   x=10+i*6;h=5+(i+g.ctx)%3*3;f[26-h:26,x:x+3]=STAR if i!=g.pos else GESTURE
  f[35:40,8:28]=CONTEXT+g.ctx;f[35:40,36:56]=POLICY
  for i,v in enumerate(g.seen[-5:]):f[45:50,8+i*9:14+i*9]=GOAL if v else POLICY
  if g.gestures:f[53:57,8:8+min(g.gestures,5)*9]=GESTURE
  if g.applied:f[56:60,40:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q548(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q548",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=self.ctx=self.gestures=0;self.seen=();self.applied=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.pos,self.ctx,self.seen,self.gestures,self.applied),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.pos,self.ctx,self.seen,self.gestures,self.applied=s
  elif a==6:
   if (self.pos,self.ctx,self.seen,self.gestures,self.applied)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
