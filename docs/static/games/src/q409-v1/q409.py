"""q409 Monsoon Delegation -- integrate two readers only at a shared weather phase."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,VIEW,MARK,CYCLE,INTEGRATE,BAD=6,10,9,14,12,5,11,7,15
def delegation(n):
 base=[1,3,4,2,3];fill=[1,2,3,4]
 return tuple(base+[fill[i%4] for i in range(n-5)])+(5,)
LEVELS=[{"name":"Two Forecasts","periods":(5,5),"plan":delegation(5)},{"name":"Unequal Readers","periods":(2,3),"plan":delegation(6)},{"name":"Nested Marks","periods":(2,4),"plan":delegation(8)},{"name":"Long Handoff","periods":(2,5),"plan":delegation(10)},{"name":"Sparse Agreement","periods":(3,4),"plan":delegation(12)},{"name":"Monsoon Delegation","periods":(4,5),"plan":delegation(20)}]
def advance(s,a,x):
 controller,views,marks,pa,pb,integrated=s;views=list(views);marks=list(marks)
 if a in (1,2,3,4):
  if a in (1,2):views.append((controller,a,(a+controller+pa+pb)%5))
  elif a==3:
   mine=[v for v in views if v[0]==controller]
   if not mine:return None
   marks.append((controller,sum(v[2] for v in mine)%5))
  else:controller=1-controller
  pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or len({m[0] for m in marks})<2:return None
  integrated=(sum((c+1)*v for c,v in marks)+len(views))%8
 return controller,tuple(views),tuple(marks),pa,pb,integrated
def target(x):
 s=(0,(),(),0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN;f[7:31,7:29]=CLOUD;f[7:31,35:57]=RAIN
  for i,(_,_,v) in enumerate(g.views[-8:]):x=9+(i%4)*5;y=11+(i//4)*10;f[y:y+6,x:x+4]=VIEW-v
  for i,(_,v) in enumerate(g.marks[-6:]):f[35+i*3:37+i*3,8:11+v*9]=MARK
  f[53:56,8:24]=CYCLE;f[57:60,40:56]=INTEGRATE if g.integrated else CLOUD
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q409(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q409",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=();self.marks=();self.pa=self.pb=self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.views,self.marks,self.pa,self.pb,self.integrated),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.views,self.marks,self.pa,self.pb,self.integrated=s
  elif a==6:
   if (self.controller,self.views,self.marks,self.pa,self.pb,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
