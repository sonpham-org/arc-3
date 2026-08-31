"""q706 Crossing Evidence -- combine disjoint marked sample views before safe stopping."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,SAMPLE0,SAMPLE1,DOCK,MARGIN,MARK0,MARK1,GOAL,BAD=6,0,11,9,14,10,7,5,13,15
LEVELS=[
 {"name":"Two Views","budget":2,"seq":(1,4,3,2,4)},
 {"name":"Second Sample","budget":3,"seq":(1,4,3,2,2,4)},
 {"name":"Early Certainty","budget":4,"seq":(1,1,4,3,2,4)},
 {"name":"Unequal Controllers","budget":5,"seq":(1,2,1,4,3,2,4)},
 {"name":"Marked Confidence","budget":6,"seq":(1,1,2,4,3,2,2,4)},
 {"name":"Crossing Evidence","budget":7,"seq":(1,2,1,1,4,3,2,2,4)}]
def advance(s,a,x):
 controller,margin,used,samples,marks,stopped=s
 if a in (1,2):
  if used>=x["budget"]:return None
  table=((3,-2),(1,2));w=table[controller][a-1];margin+=w;used+=1;samples=samples+((controller,w),)
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,margin,used),)
 elif a==5:
  if {m[0] for m in marks}!={0,1} or abs(margin)<=(x["budget"]-used)*3:return None
  stopped=(controller,margin,used,marks[-2:])
 return controller,margin,used,samples,marks,stopped
for x in LEVELS:
 s=(0,0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 assert abs(s[1])>(x["budget"]-s[2])*3;x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,0,(),(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i in range(g.cfg["budget"]):f[9:16,8+i*7:13+i*7]=DOCK if i>=g.used else SAMPLE0
  for i,(c,w) in enumerate(g.samples[-6:]):f[23:31,8+i*8:14+i*8]=SAMPLE0 if c==0 else SAMPLE1
  f[32:35,8:25]=SAMPLE0;f[32:35,31:48]=SAMPLE1
  center=32;width=min(abs(g.margin),12)*2
  if g.margin>=0:f[38:43,center:center+width]=MARGIN
  else:f[38:43,center-width:center]=SAMPLE1
  for i,m in enumerate(g.marks[-5:]):f[48:53,8+i*10:15+i*10]=MARK0 if m[0]==0 else MARK1
  f[49:52,48:52]=MARK0;f[49:52,53:57]=MARK1
  if g.stopped:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q706(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q706",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=self.margin=self.used=0;self.samples=self.marks=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.margin,self.used,self.samples,self.marks,self.stopped),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.margin,self.used,self.samples,self.marks,self.stopped=s
  elif a==6:
   if (self.controller,self.margin,self.used,self.samples,self.marks,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
