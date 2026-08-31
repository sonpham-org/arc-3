"""q410 Workbench Delegation -- integrate partial views and identity-bound handoff favors."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,VIEW,MARK,DEBT,INTEGRATE,BAD=6,10,9,14,12,5,11,7,15
LEVELS=[{"name":"Two Operators","shift":1,"plan":(1,3,4,2,3,5)},{"name":"Crossed Views","shift":2,"plan":(2,3,4,1,3,5)},{"name":"Overlapping Marks","shift":3,"plan":(1,2,3,4,2,3,5)},{"name":"Double Handoff","shift":1,"plan":(2,1,3,4,1,3,4,2,3,5)},{"name":"Remote Fixture","shift":2,"plan":(1,3,4,2,1,3,4,1,3,5)},{"name":"Workbench Delegation","shift":3,"plan":(2,1,3,4,1,3,2,4,2,1,3,5)}]
def advance(s,a,x):
 controller,views,marks,debt,obligations,integrated=s;views=list(views);marks=list(marks);debt=list(debt);obligations=list(obligations)
 if a in (1,2):views.append((controller,a,(a+controller+x["shift"]+sum(debt))%5))
 elif a==3:
  mine=[v for v in views if v[0]==controller]
  if not mine:return None
  marks.append((controller,sum(v[2] for v in mine)%5))
 elif a==4:debt[controller]+=1;obligations.append(controller);controller=1-controller
 elif a==5:
  if len({m[0] for m in marks})<2 or not obligations:return None
  integrated=(sum((c+1)*v for c,v in marks)+sum((i+1)*v for i,v in enumerate(debt)))%8;debt=[0,0];obligations=[]
 return controller,tuple(views),tuple(marks),tuple(debt),tuple(obligations),integrated
def target(x):
 s=(0,(),(),(0,0),(),0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH;f[7:31,7:29]=FIXTURE;f[7:31,35:57]=TOOL
  for i,(_,_,v) in enumerate(g.views[-8:]):x=9+(i%4)*5;y=11+(i//4)*10;f[y:y+6,x:x+4]=VIEW-v
  for i,(_,v) in enumerate(g.marks[-6:]):f[35+i*3:37+i*3,8:11+v*9]=MARK
  f[53:56,8:11+g.debt[0]*8]=DEBT;f[53:56,32:35+g.debt[1]*8]=DEBT;f[57:60,44:56]=INTEGRATE if g.integrated else FIXTURE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q410(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q410",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=();self.marks=();self.debt=(0,0);self.obligations=();self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.views,self.marks,self.debt,self.obligations,self.integrated),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.views,self.marks,self.debt,self.obligations,self.integrated=s
  elif a==6:
   if (self.controller,self.views,self.marks,self.debt,self.obligations,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
