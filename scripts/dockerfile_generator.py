
import os
import stencils

script_path = os.path.dirname(os.path.abspath(__file__))
templates = stencils.load([script_path])

dockerfile1 = stencils.render(templates['minimal'],{'processing':'cpu'},on_missing='keep')
print(dockerfile1)

dockerfile2 = stencils.render(templates['minimal'],{'processing':'cuda'},on_missing='keep')
dockerfile3 = stencils.render(templates['datascience'],{'processing':'cpu'},on_missing='keep')
dockerfile4 = stencils.render(templates['pytorch'],{'processing':'cuda'},on_missing='keep')

pass
